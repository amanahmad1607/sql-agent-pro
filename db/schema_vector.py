"""
db/schema_vector.py
Semantic Schema Management — introspects PostgreSQL and indexes
table/column descriptions into ChromaDB so the agent retrieves
only the 3–5 most relevant tables per query (prevents context bloat).
"""

from __future__ import annotations

import os
import hashlib
import json

import chromadb
import structlog
from chromadb.utils import embedding_functions
from sqlalchemy import inspect

from db.connector import get_engine

log = structlog.get_logger(__name__)

_EMBED_MODEL = "all-MiniLM-L6-v2"


def _get_chroma_client() -> chromadb.Client:
    persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
    return chromadb.PersistentClient(path=persist_dir)


def _get_collection(client: chromadb.Client) -> chromadb.Collection:
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=_EMBED_MODEL
    )
    return client.get_or_create_collection(
        name=os.getenv("CHROMA_COLLECTION", "schema_embeddings"),
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )


def _introspect_schema(schema: str = "public") -> list[dict]:
    engine = get_engine()
    inspector = inspect(engine)
    tables = []

    for table_name in inspector.get_table_names(schema=schema):
        columns = inspector.get_columns(table_name, schema=schema)
        pk = inspector.get_pk_constraint(table_name, schema=schema)
        fks = inspector.get_foreign_keys(table_name, schema=schema)

        col_lines = [
            f"  {c['name']} {c['type']} {'NOT NULL' if not c['nullable'] else ''}"
            for c in columns
        ]
        fk_notes = [
            f"{fk['constrained_columns']} → {fk['referred_table']}.{fk['referred_columns']}"
            for fk in fks
        ]

        description = (
            f"Table '{schema}.{table_name}' stores: "
            + ", ".join(c["name"] for c in columns)
            + ". "
            + (f"PK: {pk.get('constrained_columns', [])}. " if pk else "")
            + ("FK: " + "; ".join(fk_notes) + "." if fk_notes else "")
        )

        tables.append({
            "table_name": table_name,
            "schema": schema,
            "description": description,
            "ddl": f"CREATE TABLE {schema}.{table_name} (\n"
                   + ",\n".join(col_lines) + "\n);",
            "columns": [c["name"] for c in columns],
            "fk_notes": fk_notes,
        })

    log.info("schema.introspected", tables=len(tables))
    return tables


def build_schema_index(schema: str = "public", force_rebuild: bool = False) -> int:
    client = _get_chroma_client()
    collection = _get_collection(client)
    tables = _introspect_schema(schema)
    documents, metadatas, ids = [], [], []

    for t in tables:
        content_hash = hashlib.md5(t["description"].encode()).hexdigest()
        doc_id = f"{t['schema']}.{t['table_name']}"

        if not force_rebuild:
            try:
                existing = collection.get(ids=[doc_id], include=["metadatas"])
                if existing["metadatas"] and existing["metadatas"][0].get("hash") == content_hash:
                    continue
            except Exception:
                pass

        documents.append(t["description"])
        metadatas.append({
            "table_name": t["table_name"],
            "schema": t["schema"],
            "ddl": t["ddl"],
            "columns": json.dumps(t["columns"]),
            "fk_notes": json.dumps(t["fk_notes"]),
            "hash": content_hash,
        })
        ids.append(doc_id)

    if documents:
        collection.upsert(documents=documents, metadatas=metadatas, ids=ids)
        log.info("schema.index.upserted", count=len(documents))

    return len(tables)


def retrieve_relevant_schema(query: str, top_k: int = 5) -> list[dict]:
    client = _get_chroma_client()
    collection = _get_collection(client)
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
            "schema": meta["schema"],
            "ddl": meta["ddl"],
            "columns": json.loads(meta["columns"]),
            "fk_notes": json.loads(meta["fk_notes"]),
            "relevance_score": round(1 - results["distances"][0][i], 3),
            "description": results["documents"][0][i],
        })

    log.info("schema.retrieved", count=len(schemas))
    return schemas
