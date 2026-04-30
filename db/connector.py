"""
db/connector.py
Production PostgreSQL connector — QueuePool, read-only enforcement,
health-check with retry, and a clean execute_query helper.
"""

from __future__ import annotations

import os
import structlog
from functools import lru_cache
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from tenacity import retry, stop_after_attempt, wait_exponential

log = structlog.get_logger(__name__)


def _build_dsn() -> str:
    required = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise EnvironmentError(f"Missing required env vars: {', '.join(missing)}")
    return (
        f"postgresql+psycopg2://{os.environ['DB_USER']}:{os.environ['DB_PASSWORD']}"
        f"@{os.environ['DB_HOST']}:{os.environ['DB_PORT']}/{os.environ['DB_NAME']}"
    )


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """
    Singleton engine with QueuePool.
    Every connection is forced into read-only mode at the DBAPI level —
    a second layer of protection beyond DB-level permissions.
    """
    dsn = _build_dsn()
    engine = create_engine(
        dsn,
        poolclass=QueuePool,
        pool_size=int(os.getenv("DB_POOL_SIZE", 5)),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", 10)),
        pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", 30)),
        pool_pre_ping=True,
        connect_args={
            "connect_timeout": 10,
            "options": "-c statement_timeout=30000",
        },
        echo=False,
    )

    @event.listens_for(engine, "connect")
    def _set_readonly(dbapi_conn, _record):
        dbapi_conn.set_session(readonly=True, autocommit=True)
        log.debug("db.connection.readonly_set")

    log.info("db.engine.created", pool_size=engine.pool.size())
    return engine


def get_session_factory() -> sessionmaker:
    return sessionmaker(bind=get_engine(), autocommit=False, autoflush=False)


def get_db_session() -> Generator[Session, None, None]:
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
def health_check() -> bool:
    with get_engine().connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
        assert result == 1
    log.info("db.health_check.ok")
    return True


def execute_query(sql: str, params: dict | None = None) -> list[dict]:
    """Run a validated read-only SQL query and return rows as dicts."""
    with get_engine().connect() as conn:
        result = conn.execute(text(sql), params or {})
        columns = list(result.keys())
        rows = [dict(zip(columns, row)) for row in result.fetchall()]
    log.info("db.query.executed", rows=len(rows))
    return rows
