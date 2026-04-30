"""
agents/metadata_extractor.py
Unstructured text column intelligence layer.

Detects free-text columns in query results, calls Groq/LLM to extract
structured metadata (sentiment, topics, entities, urgency, summary),
and merges that back into the result rows as new columns.

Also supports indexing text columns into ChromaDB for future semantic search.
"""

from __future__ import annotations

import json
import os
import structlog
from typing import Any

log = structlog.get_logger(__name__)

_TEXT_HINTS = {
    "note", "notes", "comment", "comments", "description", "desc",
    "review", "review_text", "feedback", "body", "content", "message",
    "summary", "detail", "details", "remark", "remarks", "text",
    "narrative", "reason", "explanation",
}

_EXTRACT_SYSTEM = """You are a structured data extraction engine.
Given a JSON array of text strings, return a JSON array of metadata objects.
One object per input string. Each object must have:
{
  "sentiment": "positive"|"neutral"|"negative"|null,
  "topics": ["topic1","topic2"],
  "entities": {"people":[],"orgs":[],"dates":[],"amounts":[]},
  "urgency": "high"|"medium"|"low"|null,
  "summary": "one sentence, max 15 words"
}
Return ONLY the JSON array. No preamble, no markdown, no code fences.
"""


def detect_text_columns(rows: list[dict]) -> list[str]:
    if not rows:
        return []
    text_cols = []
    sample = rows[0]
    for col, val in sample.items():
        col_lower = col.lower().replace("_", "")
        if any(hint in col_lower for hint in _TEXT_HINTS):
            text_cols.append(col)
            continue
        if isinstance(val, str):
            avg_len = sum(len(str(r.get(col, ""))) for r in rows[:20]) / min(len(rows), 20)
            if avg_len > 40:
                text_cols.append(col)
    log.info("metadata.text_columns", cols=text_cols)
    return text_cols


def extract_metadata(values: list[str], batch_size: int = 20) -> list[dict]:
    from agents.llm import get_llm
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = get_llm()
    results = []

    for i in range(0, len(values), batch_size):
        batch = values[i: i + batch_size]
        try:
            response = llm.invoke([
                SystemMessage(content=_EXTRACT_SYSTEM),
                HumanMessage(content=json.dumps(batch, ensure_ascii=False)),
            ])
            raw = response.content.strip().strip("```json").strip("```").strip()
            results.extend(json.loads(raw))
        except Exception as exc:
            log.warning("metadata.extract.error", error=str(exc))
            results.extend([{} for _ in batch])

    return results


def enrich_results(rows: list[dict], text_columns: list[str]) -> list[dict]:
    if not rows or not text_columns:
        return rows

    enriched = [row.copy() for row in rows]

    for col in text_columns:
        values = [str(row.get(col, "") or "") for row in rows]
        metadata_list = extract_metadata(values)

        for i, meta in enumerate(metadata_list):
            if i >= len(enriched):
                break
            enriched[i][f"{col}__sentiment"] = meta.get("sentiment")
            enriched[i][f"{col}__topics"]    = ", ".join(meta.get("topics", []))
            enriched[i][f"{col}__summary"]   = meta.get("summary")
            enriched[i][f"{col}__urgency"]   = meta.get("urgency")

        log.info("metadata.enriched", col=col, rows=len(rows))

    return enriched


def index_text_column(
    rows: list[dict],
    text_column: str,
    id_column: str,
    collection_name: str,
) -> int:
    import chromadb
    from chromadb.utils import embedding_functions

    client = chromadb.PersistentClient(path=os.getenv("CHROMA_PERSIST_DIR", "./chroma_db"))
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    col = client.get_or_create_collection(name=collection_name, embedding_function=ef,
                                          metadata={"hnsw:space": "cosine"})

    docs, metas, ids = [], [], []
    for row in rows:
        text_val = str(row.get(text_column, "") or "").strip()
        row_id = str(row.get(id_column, ""))
        if not text_val or not row_id:
            continue
        docs.append(text_val)
        metas.append({k: str(v) for k, v in row.items() if k != text_column})
        ids.append(f"{collection_name}:{row_id}")

    if docs:
        col.upsert(documents=docs, metadatas=metas, ids=ids)

    log.info("metadata.indexed", collection=collection_name, count=len(docs))
    return len(docs)


def semantic_search(query: str, collection_name: str, top_k: int = 10) -> list[dict]:
    import chromadb
    from chromadb.utils import embedding_functions

    client = chromadb.PersistentClient(path=os.getenv("CHROMA_PERSIST_DIR", "./chroma_db"))
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    col = client.get_or_create_collection(name=collection_name, embedding_function=ef)

    results = col.query(query_texts=[query], n_results=min(top_k, col.count()),
                        include=["documents", "metadatas", "distances"])
    hits = []
    for i, doc in enumerate(results["documents"][0]):
        hit = results["metadatas"][0][i].copy()
        hit["_text"]  = doc
        hit["_score"] = round(1 - results["distances"][0][i], 3)
        hits.append(hit)
    return hits
