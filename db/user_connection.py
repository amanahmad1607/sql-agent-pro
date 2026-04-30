"""
db/user_connection.py
Dynamic per-user database connection manager.

Allows users to connect their own database at runtime through the UI
without touching .env or restarting the app.

Supports: PostgreSQL, MySQL, SQLite, MS SQL Server
Stores connection config in Streamlit session state.
Engine is cached per unique DSN so reconnecting with the same
credentials reuses the existing pool.
"""

from __future__ import annotations

import structlog
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional
from urllib.parse import quote_plus

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool, StaticPool

log = structlog.get_logger(__name__)

# ── Supported database types ──────────────────────────────────────────────────

DB_TYPES = {
    "PostgreSQL":  "postgresql+psycopg2",
    "MySQL":       "mysql+pymysql",
    "SQLite":      "sqlite",
    "SQL Server":  "mssql+pyodbc",
}

DB_DEFAULT_PORTS = {
    "PostgreSQL": 5432,
    "MySQL":      3306,
    "SQL Server": 1433,
    "SQLite":     None,
}

DB_DRIVERS = {
    "PostgreSQL": "psycopg2-binary",
    "MySQL":      "pymysql",
    "SQLite":     "(built-in)",
    "SQL Server": "pyodbc",
}


@dataclass
class UserConnectionConfig:
    """All parameters needed to build a user's DB connection."""
    db_type:   str = "PostgreSQL"
    host:      str = "localhost"
    port:      int = 5432
    database:  str = ""
    username:  str = ""
    password:  str = ""
    schema:    str = "public"
    ssl:       bool = False
    # SQLite only
    sqlite_path: str = ""

    @property
    def dsn(self) -> str:
        driver = DB_TYPES[self.db_type]

        if self.db_type == "SQLite":
            return f"sqlite:///{self.sqlite_path}"

        if self.db_type == "SQL Server":
            return (
                f"mssql+pyodbc://{quote_plus(self.username)}:{quote_plus(self.password)}"
                f"@{self.host}:{self.port}/{self.database}"
                f"?driver=ODBC+Driver+17+for+SQL+Server"
            )

        return (
            f"{driver}://{quote_plus(self.username)}:{quote_plus(self.password)}"
            f"@{self.host}:{self.port}/{self.database}"
            + ("?sslmode=require" if self.ssl else "")
        )

    @property
    def display_dsn(self) -> str:
        """Safe version with password masked — for display only."""
        if self.db_type == "SQLite":
            return f"sqlite:///{self.sqlite_path}"
        driver = DB_TYPES[self.db_type]
        return (
            f"{driver}://{self.username}:****"
            f"@{self.host}:{self.port}/{self.database}"
        )

    def is_complete(self) -> bool:
        if self.db_type == "SQLite":
            return bool(self.sqlite_path)
        return all([self.host, self.database, self.username, self.password])


# ── Engine cache (keyed by DSN so same config reuses pool) ───────────────────

_engine_cache: dict[str, Engine] = {}

def get_user_engine(config: UserConnectionConfig) -> Engine:
    dsn = config.dsn
    if dsn in _engine_cache:
        return _engine_cache[dsn]

    # Initialize empty containers
    connect_args = {}
    pool_kwargs = {}

    if config.db_type == "PostgreSQL":
        connect_args = {
            "connect_timeout": 10,
            "options": "-c statement_timeout=30000",
        }
        pool_kwargs = {
            "poolclass": QueuePool,
            "pool_size": 3,
            "max_overflow": 5,
            "pool_timeout": 20,
            "pool_pre_ping": True,
        }
    elif config.db_type == "SQLite":
        # FIXED: Put connection-level flags here
        connect_args = {"check_same_thread": False}
        # FIXED: Put pool-level flags here (DO NOT put connect_args inside this dict)
        pool_kwargs = {
            "poolclass": StaticPool,
        }
    else:
        pool_kwargs = {
            "pool_pre_ping": True,
            "pool_size": 3,
        }

    # Now create_engine gets connect_args once, and pool_kwargs (minus connect_args) via unpacking
    engine = create_engine(
        dsn, 
        connect_args=connect_args, 
        echo=False, 
        **pool_kwargs
    )

    # ... (rest of your existing event listener code) ...
    
    _engine_cache[dsn] = engine
    return engine



def test_user_connection(config: UserConnectionConfig) -> tuple[bool, str]:
    """
    Test a user's connection. Returns (success, message).
    Does NOT cache the engine on failure.
    """
    try:
        engine = get_user_engine(config)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "Connected successfully"
    except Exception as exc:
        # Remove from cache so a retry creates a fresh engine
        _engine_cache.pop(config.dsn, None)
        return False, str(exc)


def execute_user_query(config: UserConnectionConfig, sql: str) -> list[dict]:
    """Execute a validated SQL query using the user's connection."""
    engine = get_user_engine(config)
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        columns = list(result.keys())
        rows = [dict(zip(columns, row)) for row in result.fetchall()]
    log.info("user_query.executed", rows=len(rows), db=config.database)
    return rows


def get_user_tables(config: UserConnectionConfig) -> list[str]:
    """Introspect the user's database and return all table names."""
    from sqlalchemy import inspect
    engine = get_user_engine(config)
    inspector = inspect(engine)
    schema = config.schema if config.db_type == "PostgreSQL" else None
    try:
        return sorted(inspector.get_table_names(schema=schema))
    except Exception:
        return inspector.get_table_names()


def build_user_schema_index(config: UserConnectionConfig) -> int:
    """
    Introspect the user's DB and build a ChromaDB schema index
    scoped to their connection (collection name = sanitized DSN hash).
    Returns number of tables indexed.
    """
    import hashlib
    import json
    import chromadb
    import os
    from chromadb.utils import embedding_functions
    from sqlalchemy import inspect

    engine     = get_user_engine(config)
    inspector  = inspect(engine)
    schema     = config.schema if config.db_type == "PostgreSQL" else None
    table_names = get_user_tables(config)

    # Unique collection per user connection
    conn_hash  = hashlib.md5(config.display_dsn.encode()).hexdigest()[:8]
    collection_name = f"user_{conn_hash}"

    persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
    client = chromadb.PersistentClient(path=persist_dir)
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )

    documents, metadatas, ids = [], [], []
    for table_name in table_names:
        try:
            cols = inspector.get_columns(table_name, schema=schema)
            fks  = inspector.get_foreign_keys(table_name, schema=schema)
            pk   = inspector.get_pk_constraint(table_name, schema=schema)

            col_lines = [
                f"  {c['name']} {c['type']}" for c in cols
            ]
            fk_notes = [
                f"{fk['constrained_columns']} → {fk['referred_table']}.{fk['referred_columns']}"
                for fk in fks
            ]
            ddl = (
                f"CREATE TABLE {table_name} (\n"
                + ",\n".join(col_lines) + "\n);"
            )
            description = (
                f"Table '{table_name}' contains: "
                + ", ".join(c["name"] for c in cols)
                + (f". PK: {pk.get('constrained_columns', [])}." if pk else "")
                + (f" FK: {'; '.join(fk_notes)}." if fk_notes else "")
            )

            documents.append(description)
            metadatas.append({
                "table_name": table_name,
                "schema": schema or "default",
                "ddl": ddl,
                "columns": json.dumps([c["name"] for c in cols]),
                "fk_notes": json.dumps(fk_notes),
            })
            ids.append(f"{collection_name}:{table_name}")
        except Exception as exc:
            log.warning("user_schema.skip_table", table=table_name, error=str(exc))

    if documents:
        collection.upsert(documents=documents, metadatas=metadatas, ids=ids)

    log.info("user_schema.indexed", collection=collection_name, tables=len(documents))
    return len(documents), collection_name


def retrieve_user_schema(
    collection_name: str,
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """Semantic schema retrieval scoped to a user's indexed collection."""
    import json
    import os
    import chromadb
    from chromadb.utils import embedding_functions

    persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
    client = chromadb.PersistentClient(path=persist_dir)
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    collection = client.get_or_create_collection(
        name=collection_name, embedding_function=ef
    )
    count = collection.count()
    if count == 0:
        return []

    results = collection.query(
        query_texts=[query],
        n_results=min(top_k, count),
        include=["documents", "metadatas", "distances"],
    )
    schemas = []
    for i, meta in enumerate(results["metadatas"][0]):
        schemas.append({
            "table_name": meta["table_name"],
            "schema": meta.get("schema", ""),
            "ddl": meta["ddl"],
            "columns": json.loads(meta.get("columns", "[]")),
            "fk_notes": json.loads(meta.get("fk_notes", "[]")),
            "relevance_score": round(1 - results["distances"][0][i], 3),
        })
    return schemas
