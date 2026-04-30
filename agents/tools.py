"""
agents/tools.py
LangChain @tool definitions consumed by the LangGraph nodes.
"""

from __future__ import annotations

import json
import structlog
from typing import Any

from langchain_core.tools import tool

from db.connector import execute_query
from db.schema_vector import retrieve_relevant_schema
from utils.guardrails import validate_and_sanitize, mask_pii

log = structlog.get_logger(__name__)


@tool
def retrieve_schema(query: str, top_k: int = 5) -> str:
    """
    Semantic schema retrieval — returns DDL for the most relevant tables.
    """
    schemas = retrieve_relevant_schema(query, top_k=top_k)
    if not schemas:
        return "No schema found. Run: python cli.py index-schema"

    parts = []
    for s in schemas:
        block = [
            f"-- {s['schema']}.{s['table_name']} (relevance: {s['relevance_score']})",
            s["ddl"],
        ]
        if s["fk_notes"]:
            block.append("-- FK: " + "; ".join(s["fk_notes"]))
        parts.append("\n".join(block))
    return "\n\n".join(parts)


@tool
def execute_sql(sql: str) -> dict[str, Any]:
    """
    Validate and execute a SQL SELECT query.
    Returns success/error status, rows, columns, and row count.
    """
    guard = validate_and_sanitize(sql)
    if not guard.is_safe:
        log.warning("guardrail.blocked", violation=guard.violation)
        return {
            "success": False,
            "error": f"Security violation: {guard.violation}",
            "rows": [],
            "columns": [],
            "row_count": 0,
        }

    try:
        rows = execute_query(guard.safe_sql)

        # Optional PII masking on results
        rows_str = mask_pii(json.dumps(rows, default=str))
        rows = json.loads(rows_str)

        columns = list(rows[0].keys()) if rows else []
        log.info("tool.execute_sql.ok", rows=len(rows))
        return {
            "success": True,
            "rows": rows,
            "columns": columns,
            "row_count": len(rows),
            "executed_sql": guard.safe_sql,
            "error": None,
        }

    except Exception as exc:
        log.error("tool.execute_sql.error", error=str(exc))
        return {
            "success": False,
            "error": str(exc),
            "rows": [],
            "columns": [],
            "row_count": 0,
        }


def format_schema_context(schemas: list[dict]) -> str:
    parts = []
    for s in schemas:
        block = f"-- {s['schema']}.{s['table_name']}\n{s['ddl']}"
        if s["fk_notes"]:
            block += "\n-- FK: " + "; ".join(s["fk_notes"])
        parts.append(block)
    return "\n\n".join(parts)
