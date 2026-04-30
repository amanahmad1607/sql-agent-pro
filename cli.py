"""
cli.py
Operator CLI — index-schema, health-check, run-query, export-schema.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dotenv import load_dotenv

load_dotenv()

from utils.observability import configure as configure_logging
configure_logging()


def cmd_index_schema(args):
    from db.schema_vector import build_schema_index
    schema = args.schema or os.getenv("DB_SCHEMA", "public")
    print(f"Indexing schema '{schema}' (force={args.force})…")
    n = build_schema_index(schema=schema, force_rebuild=args.force)
    print(f"✓ Indexed {n} tables.")


def cmd_health_check(_args):
    from agents.llm import get_provider_info
    info = get_provider_info()
    print(f"Provider : {info['provider'].upper()} / {info['model']}")

    print("Checking PostgreSQL…")
    try:
        from db.connector import health_check
        health_check()
        print("✓ PostgreSQL: OK")
    except Exception as e:
        print(f"✗ PostgreSQL: {e}")
        sys.exit(1)

    print("Checking ChromaDB…")
    try:
        import chromadb
        client = chromadb.PersistentClient(
            path=os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
        )
        client.heartbeat()
        print("✓ ChromaDB: OK")
    except Exception as e:
        print(f"✗ ChromaDB: {e}")
        sys.exit(1)


def cmd_run_query(args):
    from agents.graph import run_agent
    question = args.question or input("Question: ")
    print(f"\nQuestion : {question}\n{'─'*60}")
    result = run_agent(question)
    er = result.get("execution_result") or {}

    print(f"\n📝 SQL:\n{result.get('generated_sql','N/A')}\n")
    print(f"📊 Rows    : {er.get('row_count', 0)}")
    print(f"🔄 Retries : {result.get('retry_count', 0)}")
    print(f"\n💡 Answer:\n{result.get('final_answer','No answer.')}\n")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"Full result saved to {args.output}")


def cmd_export_schema(args):
    from db.schema_vector import _introspect_schema
    schema = args.schema or os.getenv("DB_SCHEMA", "public")
    tables = _introspect_schema(schema)
    out = args.output or "schema_export.json"
    with open(out, "w") as f:
        json.dump(tables, f, indent=2, default=str)
    print(f"✓ Exported {len(tables)} tables to {out}")


def main():
    parser = argparse.ArgumentParser(description="SQL Agent Pro CLI")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("index-schema")
    p.add_argument("--schema", default=None)
    p.add_argument("--force", action="store_true")

    sub.add_parser("health-check")

    p = sub.add_parser("run-query")
    p.add_argument("--question", "-q", default=None)
    p.add_argument("--output",   "-o", default=None)

    p = sub.add_parser("export-schema")
    p.add_argument("--schema", default=None)
    p.add_argument("--output", "-o", default=None)

    args = parser.parse_args()
    dispatch = {
        "index-schema":  cmd_index_schema,
        "health-check":  cmd_health_check,
        "run-query":     cmd_run_query,
        "export-schema": cmd_export_schema,
    }
    if args.command in dispatch:
        dispatch[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
