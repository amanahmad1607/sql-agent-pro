"""
utils/observability.py
Structured logging (structlog) + optional LangSmith tracing.
Call configure() once at startup.
"""

from __future__ import annotations

import os
import sys
import logging
import structlog


def configure(level: str | None = None) -> None:
    log_level = level or os.getenv("LOG_LEVEL", "INFO").upper()
    is_dev = os.getenv("ENV", "development").lower() in ("dev", "development", "local")

    logging.basicConfig(format="%(message)s", stream=sys.stdout,
                        level=getattr(logging, log_level, logging.INFO))

    for noisy in ("httpx", "httpcore", "groq", "chromadb", "urllib3", "sentence_transformers"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    shared = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    processors = shared + (
        [structlog.dev.ConsoleRenderer(colors=True)]
        if is_dev else
        [structlog.processors.dict_tracebacks, structlog.processors.JSONRenderer()]
    )

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level, logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    log = structlog.get_logger("observability")
    log.info("logging.configured", level=log_level, mode="dev" if is_dev else "prod")

    # LangSmith
    if os.getenv("LANGCHAIN_API_KEY") and os.getenv("LANGCHAIN_TRACING_V2", "false") == "true":
        os.environ.setdefault("LANGCHAIN_PROJECT", "sql-agent-pro")
        log.info("langsmith.enabled", project=os.environ.get("LANGCHAIN_PROJECT"))
    else:
        log.info("langsmith.disabled")