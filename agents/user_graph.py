"""
agents/user_graph.py
A variant of the main LangGraph agent that runs against a user-supplied
database connection instead of the env-configured one.

Accepts a UserConnectionConfig and a ChromaDB collection_name at runtime,
so every user query goes to their own DB with their own schema index.
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
from db.user_connection import (
    UserConnectionConfig,
    execute_user_query,
    retrieve_user_schema,
)
from utils.guardrails import validate_and_sanitize

log = structlog.get_logger(__name__)

MAX_RETRIES   = int(os.getenv("MAX_RETRIES", 3))
GROQ_DELAY    = float(os.getenv("GROQ_RETRY_DELAY", 1.0))


# ── State ─────────────────────────────────────────────────────────────────────

class UserAgentState(TypedDict):
    question:         str
    config:           dict          # UserConnectionConfig serialized as dict
    collection_name:  str
    schema_context:   str
    annotation:       Optional[dict]
    generated_sql:    Optional[str]
    execution_result: Optional[dict]
    retry_count:      int
    error_history:    list[str]
    final_answer:     Optional[str]
    messages:         Annotated[list, add_messages]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _config_from_dict(d: dict) -> UserConnectionConfig:
    from db.user_connection import UserConnectionConfig
    return UserConnectionConfig(**d)


def _format_schema(schemas: list[dict]) -> str:
    parts = []
    for s in schemas:
        block = f"-- {s.get('schema','')}.{s['table_name']}\n{s['ddl']}"
        if s.get("fk_notes"):
            block += "\n-- FK: " + "; ".join(s["fk_notes"])
        parts.append(block)
    return "\n\n".join(parts)


# ── Nodes ─────────────────────────────────────────────────────────────────────

def annotate_query(state: UserAgentState) -> dict:
    log.info("user_agent.annotate", question=state["question"][:80])
    llm = get_llm()

    schemas = retrieve_user_schema(
        state["collection_name"], state["question"], top_k=5
    )
    schema_context = _format_schema(schemas)

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

    return {
        "schema_context": schema_context,
        "annotation": annotation,
        "retry_count": 0,
        "error_history": [],
        "messages": [HumanMessage(content=state["question"])],
    }


def generate_sql(state: UserAgentState) -> dict:
    retry = state["retry_count"]
    log.info("user_agent.generate_sql", retry=retry)
    llm = get_llm()

    if retry > 0 and os.getenv("LLM_PROVIDER", "groq").lower() == "groq":
        time.sleep(GROQ_DELAY)

    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    for ex in FEW_SHOT_EXAMPLES:
        messages.append(HumanMessage(content=ex["question"]))
        messages.append(AIMessage(content=ex["sql"]))

    if retry == 0:
        enriched = state.get("annotation", {}).get(
            "enriched_question", state["question"]
        )
        content = f"SCHEMA:\n{state['schema_context']}\n\nQUESTION: {enriched}"
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
    log.info("user_agent.sql_generated", preview=sql[:100])
    return {"generated_sql": sql, "messages": [AIMessage(content=sql)]}


def execute_sql_node(state: UserAgentState) -> dict:
    log.info("user_agent.execute_sql")
    config = _config_from_dict(state["config"])

    guard = validate_and_sanitize(state["generated_sql"])
    if not guard.is_safe:
        return {
            "execution_result": {
                "success": False,
                "error": f"Security violation: {guard.violation}",
                "rows": [], "columns": [], "row_count": 0,
            }
        }
    try:
        rows    = execute_user_query(config, guard.safe_sql)
        columns = list(rows[0].keys()) if rows else []
        return {
            "execution_result": {
                "success": True,
                "rows": rows,
                "columns": columns,
                "row_count": len(rows),
                "executed_sql": guard.safe_sql,
                "error": None,
            }
        }
    except Exception as exc:
        log.error("user_agent.execute_error", error=str(exc))
        return {
            "execution_result": {
                "success": False,
                "error": str(exc),
                "rows": [], "columns": [], "row_count": 0,
            }
        }


def check_result(state: UserAgentState) -> str:
    result = state["execution_result"]
    if result["success"]:
        return "format_answer"
    if state["retry_count"] + 1 >= MAX_RETRIES:
        return "end_with_error"
    return "generate_sql"


def increment_retry(state: UserAgentState) -> dict:
    er = state["execution_result"]
    return {
        "retry_count": state["retry_count"] + 1,
        "error_history": state["error_history"] + [er.get("error", "Unknown")],
    }


def format_answer(state: UserAgentState) -> dict:
    llm    = get_llm()
    result = state["execution_result"]
    prompt = SUMMARISATION_PROMPT.format(
        question=state["question"],
        sql=state["generated_sql"],
        row_count=result["row_count"],
        sample_data=json.dumps(result["rows"][:5], indent=2, default=str),
    )
    response = llm.invoke([
        SystemMessage(content="You are a concise data analyst."),
        HumanMessage(content=prompt),
    ])
    return {"final_answer": response.content}


def end_with_error(state: UserAgentState) -> dict:
    errors = "\n".join(
        f"Attempt {i+1}: {e}" for i, e in enumerate(state["error_history"])
    )
    return {"final_answer": f"Could not generate a valid query after {MAX_RETRIES} attempts.\n\n{errors}"}


# ── Build graph ───────────────────────────────────────────────────────────────

def build_user_graph():
    g = StateGraph(UserAgentState)
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
        "execute_sql", check_result,
        {"format_answer": "format_answer",
         "generate_sql":  "increment_retry",
         "end_with_error":"end_with_error"},
    )
    g.add_edge("increment_retry", "generate_sql")
    g.add_edge("format_answer",   END)
    g.add_edge("end_with_error",  END)
    return g.compile()


_user_graph = build_user_graph()


def run_user_agent(
    question: str,
    config: UserConnectionConfig,
    collection_name: str,
) -> dict[str, Any]:
    """Public entry point called from the Streamlit UI."""
    initial: UserAgentState = {
        "question":         question,
        "config":           config.__dict__,
        "collection_name":  collection_name,
        "schema_context":   "",
        "annotation":       None,
        "generated_sql":    None,
        "execution_result": None,
        "retry_count":      0,
        "error_history":    [],
        "final_answer":     None,
        "messages":         [],
    }
    final = _user_graph.invoke(initial)
    er    = final.get("execution_result") or {}
    log.info("user_agent.complete",
             success=er.get("success", False),
             retries=final["retry_count"])
    return final
