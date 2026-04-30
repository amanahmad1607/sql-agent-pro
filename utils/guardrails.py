"""
utils/guardrails.py
4-layer SQL security pipeline:
  1. sqlglot AST parse  — rejects non-SELECT and embedded mutations
  2. Regex fallback     — catches keyword obfuscation
  3. LIMIT injection    — hard row cap that can't be bypassed
  4. Presidio PII mask  — optional, activated via ENABLE_PII_MASKING=true
"""

from __future__ import annotations

import os
import re
import structlog
from dataclasses import dataclass
from typing import Optional

import sqlglot
from sqlglot import exp

log = structlog.get_logger(__name__)

_BLOCKED_TYPES = (
    exp.Drop, exp.Delete, exp.Update, exp.Insert,
    exp.Create, exp.Alter, exp.Grant, exp.Revoke,
    exp.TruncateTable, exp.Transaction,
)

_BLOCKED_RE = re.compile(
    r"\b(DROP|DELETE|UPDATE|INSERT|CREATE|ALTER|TRUNCATE|GRANT|REVOKE"
    r"|EXEC|EXECUTE|xp_|sp_|LOAD\s+DATA|INTO\s+OUTFILE)\b",
    re.IGNORECASE,
)

_MAX_ROWS = int(os.getenv("MAX_ROWS", 1000))


@dataclass
class GuardrailResult:
    is_safe: bool
    safe_sql: Optional[str]
    violation: Optional[str]


def validate_and_sanitize(sql: str) -> GuardrailResult:
    sql = sql.strip().rstrip(";")

    # Layer 1 — AST
    try:
        statements = sqlglot.parse(sql, dialect="postgres")
    except sqlglot.errors.ParseError as exc:
        return GuardrailResult(False, None, f"SQL parse error: {exc}")

    if len(statements) > 1:
        return GuardrailResult(False, None, "Multiple statements not allowed.")

    stmt = statements[0]
    if not isinstance(stmt, exp.Select):
        return GuardrailResult(False, None,
                               f"Only SELECT is permitted. Got: {type(stmt).__name__}")

    for node in stmt.walk():
        if isinstance(node, _BLOCKED_TYPES):
            return GuardrailResult(False, None,
                                   f"Blocked statement type: {type(node).__name__}")

    # Layer 2 — Regex
    if _BLOCKED_RE.search(sql):
        match = _BLOCKED_RE.search(sql)
        return GuardrailResult(False, None,
                               f"Blocked keyword: {match.group(0)}")

    # Layer 3 — LIMIT injection
    safe_sql = f"SELECT * FROM (\n{sql}\n) AS __limited__ LIMIT {_MAX_ROWS}"

    log.info("guardrail.passed", preview=sql[:80])
    return GuardrailResult(True, safe_sql, None)


# ── PII masking ───────────────────────────────────────────────────────────────

_analyzer = None
_anonymizer = None


def _init_presidio():
    global _analyzer, _anonymizer
    if _analyzer is None:
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine
        _analyzer = AnalyzerEngine()
        _anonymizer = AnonymizerEngine()


def mask_pii(text: str, language: str = "en") -> str:
    if os.getenv("ENABLE_PII_MASKING", "false").lower() != "true":
        return text
    _init_presidio()
    results = _analyzer.analyze(text=text, language=language)
    return _anonymizer.anonymize(text=text, analyzer_results=results).text
