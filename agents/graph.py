"""
agents/graph.py
LangGraph self-correcting SQL agent.

Flow:
  annotate_query → generate_sql → execute_sql → check_result
                                       ↑               |
                                  increment_retry ◄─── ┘ (on error, ≤ MAX_RETRIES)
                                                        ↓ (on success)
                                                  format_answer → END

Groq-specific:
  - GROQ_RETRY_DELAY env var adds a pause before retry calls to stay within
    rate limits on the free tier (default 1.0s).
  - max_tokens capped at 4096 to avoid truncation on smaller Groq models.
"""

from __future__ import annotations

import json
import os
import time
from typing import Annotated, Any, Optional, TypedDict

import structlog
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from agents.llm import get_llm
from agents.prompts import (
    ANNOTATION_PROMPT,
    CORRECTION_PROMPT,
    FEW_SHOT_EXAMPLES,
    SUMMARISATION_PROMPT,
    SYSTEM_PROMPT,
)
from agents.tools import execute_sql, format_schema_context
from db.schema_vector import retrieve_relevant_schema

log = structlog.get_logger(__name__)

MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))
GROQ_RETRY_DELAY = float(os.getenv("GROQ_RETRY_DELAY", 1.0))


# ─── Agent State ─────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    question: str
    schema_context: str
    annotation: Optional[dict]
    generated_sql: Optional[str]
    execution_result: Optional[dict]
    retry_count: int
    error_history: list[str]
    final_answer: Optional[str]
    messages: Annotated[list, add_messages]


# ─── Nodes ───────────────────────────────────────────────────────────────────

def annotate_query(state: AgentState) -> dict:
    """
    Retrieve relevant schema via ChromaDB, then ask the LLM to enrich
    the question with concrete table/column references.
    """
    log.info("node.annotate_query", question=state["question"][:80])
    llm = get_llm()

    schemas = retrieve_relevant_schema(state["question"], top_k=5)
    schema_context = format_schema_context(schemas)

    prompt = ANNOTATION_PROMPT.format(
        question=state["question"],
        schema_context=schema_context,
    )

    response = llm.invoke([
        SystemMessage(content="You are a SQL schema analyst. Return only valid JSON."),
        HumanMessage(content=prompt),
    ])

    try:
        raw = response.content.strip().strip("```json").strip("```").strip()
        annotation = json.loads(raw)
    except json.JSONDecodeError:
        annotation = {"enriched_question": state["question"]}

    log.info("node.annotate_query.done", tables=annotation.get("tables_needed", []))
    return {
        "schema_context": schema_context,
        "annotation": annotation,
        "retry_count": 0,
        "error_history": [],
        "messages": [HumanMessage(content=state["question"])],
    }


def generate_sql(state: AgentState) -> dict:
    """
    Generate (or regenerate on retry) the SQL query.
    Includes rate-limit pause for Groq free-tier users.
    """
    retry = state["retry_count"]
    log.info("node.generate_sql", retry=retry)
    llm = get_llm()

    # Groq rate-limit safety pause on retries
    if retry > 0 and os.getenv("LLM_PROVIDER", "groq").lower() == "groq":
        time.sleep(GROQ_RETRY_DELAY)

    # Build messages with few-shot examples
    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    for ex in FEW_SHOT_EXAMPLES:
        messages.append(HumanMessage(content=ex["question"]))
        messages.append(AIMessage(content=ex["sql"]))

    if retry == 0:
        enriched = state.get("annotation", {}).get(
            "enriched_question", state["question"]
        )
        content = (
            f"SCHEMA:\n{state['schema_context']}\n\n"
            f"QUESTION: {enriched}"
        )
    else:
        content = CORRECTION_PROMPT.format(
            error=state["error_history"][-1],
            failed_sql=state["generated_sql"],
            schema_context=state["schema_context"],
            question=state["question"],
        )

    messages.append(HumanMessage(content=content))
    response = llm.invoke(messages)

    sql = response.content.strip().strip("```sql").strip("```").strip()
    log.info("node.generate_sql.done", preview=sql[:100])
    return {
        "generated_sql": sql,
        "messages": [AIMessage(content=sql)],
    }


def execute_sql_node(state: AgentState) -> dict:
    """Run the generated SQL through guardrails then the DB."""
    log.info("node.execute_sql")
    result = execute_sql.invoke({"sql": state["generated_sql"]})
    return {"execution_result": result}


def check_result(state: AgentState) -> str:
    """
    Routing node — returns next node name:
      format_answer   → query succeeded
      generate_sql    → error, retry available
      end_with_error  → max retries exceeded
    """
    result = state["execution_result"]

    if result["success"]:
        log.info("node.check_result.success", rows=result["row_count"])
        return "format_answer"

    retry = state["retry_count"] + 1
    if retry >= MAX_RETRIES:
        log.warning("node.check_result.max_retries")
        return "end_with_error"

    log.info("node.check_result.retry", attempt=retry, error=result["error"][:80])
    return "generate_sql"


def increment_retry(state: AgentState) -> dict:
    result = state["execution_result"]
    return {
        "retry_count": state["retry_count"] + 1,
        "error_history": state["error_history"] + [result.get("error", "Unknown error")],
    }


def format_answer(state: AgentState) -> dict:
    """Summarise the query result in natural language."""
    llm = get_llm()
    result = state["execution_result"]
    sample = result["rows"][:5]

    prompt = SUMMARISATION_PROMPT.format(
        question=state["question"],
        sql=state["generated_sql"],
        row_count=result["row_count"],
        sample_data=json.dumps(sample, indent=2, default=str),
    )

    response = llm.invoke([
        SystemMessage(content="You are a concise data analyst. Write short, specific insights."),
        HumanMessage(content=prompt),
    ])
    return {"final_answer": response.content}


def end_with_error(state: AgentState) -> dict:
    errors = "\n".join(
        f"Attempt {i+1}: {e}" for i, e in enumerate(state["error_history"])
    )
    return {
        "final_answer": (
            f"Could not generate a valid query after {MAX_RETRIES} attempts.\n\n{errors}"
        )
    }


# ─── Build the graph ──────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    g = StateGraph(AgentState)

    g.add_node("annotate_query",  annotate_query)
    g.add_node("generate_sql",    generate_sql)
    g.add_node("execute_sql",     execute_sql_node)
    g.add_node("increment_retry", increment_retry)
    g.add_node("format_answer",   format_answer)
    g.add_node("end_with_error",  end_with_error)

    g.add_edge(START, "annotate_query")
    g.add_edge("annotate_query", "generate_sql")
    g.add_edge("generate_sql",   "execute_sql")

    g.add_conditional_edges(
        "execute_sql",
        check_result,
        {
            "format_answer":  "format_answer",
            "generate_sql":   "increment_retry",
            "end_with_error": "end_with_error",
        },
    )

    g.add_edge("increment_retry", "generate_sql")
    g.add_edge("format_answer",   END)
    g.add_edge("end_with_error",  END)

    return g.compile()


# Singleton compiled graph
agent_graph = build_graph()


def run_agent(question: str) -> dict[str, Any]:
    """Public entry point for the Streamlit UI and CLI."""
    initial: AgentState = {
        "question": question,
        "schema_context": "",
        "annotation": None,
        "generated_sql": None,
        "execution_result": None,
        "retry_count": 0,
        "error_history": [],
        "final_answer": None,
        "messages": [],
    }
    final = agent_graph.invoke(initial)
    er = final.get("execution_result") or {}
    log.info("agent.complete",
             success=er.get("success", False),
             retries=final["retry_count"])
    return final
