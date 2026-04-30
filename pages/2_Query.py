"""
pages/2_Query.py
Query page — uses the user's connected database (from session state).
Full feature set: answer, data table, auto-chart, SQL viewer, debug panel,
query history, and metadata enrichment toggle.
"""

from __future__ import annotations

import os
import time
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Query — SQL Agent Pro",
    page_icon="💬",
    layout="wide",
)

# ── Guard: must be connected first ───────────────────────────────────────────
if not st.session_state.get("user_connected"):
    st.warning("No database connected yet.")
    st.info("Please connect your database first.")
    if st.button("🔌 Connect a database"):
        st.switch_page("pages/1_Connect_Database.py")
    st.stop()

from agents.user_graph import run_user_agent
from agents.llm import get_provider_info
from db.user_connection import UserConnectionConfig

cfg: UserConnectionConfig = st.session_state.user_config
collection_name: str      = st.session_state.user_collection
tables: list[str]         = st.session_state.user_tables

# ── Init query history ────────────────────────────────────────────────────────
if "user_query_history" not in st.session_state:
    st.session_state.user_query_history = []
if "user_last_result" not in st.session_state:
    st.session_state.user_last_result = None

# ── Cached agent call ─────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def cached_run(question: str, collection: str, config_repr: str) -> dict:
    """
    config_repr is just a stable string key for the cache —
    the real config comes from session state.
    """
    return run_user_agent(question, cfg, collection)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    info = get_provider_info()
    provider_icon = {"groq": "🟢", "openai": "🔵", "anthropic": "🟣"}.get(info["provider"], "⚪")
    st.markdown("### ⚡ SQL Agent Pro")
    st.caption(f"{provider_icon} **{info['provider'].upper()}** · `{info['model']}`")
    st.divider()

    st.markdown("**Connected database**")
    st.code(cfg.display_dsn, language=None)

    if st.button("🔌 Change connection", use_container_width=True):
        st.switch_page("pages/1_Connect_Database.py")

    st.divider()
    st.markdown("**Indexed tables**")
    for t in tables:
        st.code(t, language=None)

    st.divider()
    st.subheader("🛡 Guardrails")
    st.metric("Max rows",    os.getenv("MAX_ROWS", 1000))
    st.metric("Max retries", os.getenv("MAX_RETRIES", 3))

    enrich = st.toggle(
        "Enrich text columns",
        value=False,
        help="Extract sentiment, topics, and summary from free-text columns in results.",
    )

    st.divider()
    st.caption("SQL Agent Pro · v2.0.0")


# ── Main ──────────────────────────────────────────────────────────────────────
st.title("💬 Query your database")
st.caption(
    f"Connected to **{cfg.database}** · "
    f"{len(tables)} tables · "
    f"Powered by **{info['provider'].upper()} / {info['model']}**"
)

# ── Smart example generator ───────────────────────────────────────────────────
GENERIC_EXAMPLES = [
    "Show me all tables and their row counts",
    "What are the top 10 records in the largest table?",
    "Show me recent records from the last 7 days",
    "Count records grouped by status or category",
    "Find any duplicate records",
]

table_examples = [f"Show me all records from {t}" for t in tables[:3]]
all_examples   = table_examples + GENERIC_EXAMPLES

st.subheader("Ask a question")
example = st.selectbox(
    "Examples",
    ["— pick an example or type below —"] + all_examples,
    label_visibility="collapsed",
)

question = st.text_area(
    "Your question",
    value="" if example.startswith("—") else example,
    height=90,
    placeholder=f"e.g. Show me the top 10 rows from {tables[0] if tables else 'my_table'}",
    label_visibility="collapsed",
)

c1, c2, c3 = st.columns([1, 1, 6])
with c1:
    run = st.button("▶ Run", type="primary", use_container_width=True)
with c2:
    if st.button("✕ Clear", use_container_width=True):
        st.session_state.user_query_history = []
        st.session_state.user_last_result   = None
        cached_run.clear()
        st.rerun()

# ── Execute ───────────────────────────────────────────────────────────────────
if run and question.strip():
    with st.spinner(f"🤖 {info['provider'].upper()} is querying your database…"):
        t0 = time.time()
        try:
            config_repr = cfg.display_dsn
            result = cached_run(question.strip(), collection_name, config_repr)
            result["elapsed"]   = round(time.time() - t0, 2)
            result["timestamp"] = datetime.now().strftime("%H:%M:%S")

            # Optional metadata enrichment
            if enrich and result.get("execution_result", {}).get("rows"):
                from agents.metadata_extractor import detect_text_columns, enrich_results
                rows     = result["execution_result"]["rows"]
                text_cols = detect_text_columns(rows)
                if text_cols:
                    with st.spinner(f"Enriching text columns: {text_cols}…"):
                        result["execution_result"]["rows"] = enrich_results(rows, text_cols)
                        result["enriched_columns"] = text_cols

            st.session_state.user_last_result = result
            st.session_state.user_query_history.insert(0, result)
        except Exception as exc:
            st.error(f"Agent error: {exc}")

# ── Display result ────────────────────────────────────────────────────────────
result = st.session_state.user_last_result
if result:
    er      = result.get("execution_result") or {}
    success = er.get("success", False)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Status",   "✅ Success" if success else "❌ Failed")
    m2.metric("Rows",     er.get("row_count", 0))
    m3.metric("Retries",  result.get("retry_count", 0))
    m4.metric("Time",     f"{result.get('elapsed', '—')}s")
    m5.metric("Database", cfg.database)

    if result.get("enriched_columns"):
        st.info(f"Text columns enriched: {', '.join(result['enriched_columns'])}")

    st.divider()

    t_ans, t_data, t_sql, t_debug = st.tabs(
        ["💡 Answer", "📊 Data & Chart", "🔧 SQL", "🔬 Debug"]
    )

    with t_ans:
        st.info(result.get("final_answer") or "No answer generated.")

    with t_data:
        rows = er.get("rows", [])
        if rows:
            df = pd.DataFrame(rows)

            num_cols  = df.select_dtypes("number").columns.tolist()
            date_cols = [c for c in df.columns
                         if any(k in c.lower() for k in ("date","month","year","time","day","week"))]
            cat_cols  = [c for c in df.select_dtypes("object").columns.tolist()
                         if not c.endswith(("__sentiment","__topics","__summary","__urgency"))]

            if num_cols:
                st.subheader("Auto Chart")
                chart_metric = st.selectbox("Metric to chart", num_cols, key="user_chart_col")
                if date_cols:
                    fig = px.line(df, x=date_cols[0], y=chart_metric,
                                  title=f"{chart_metric} over time",
                                  template="plotly_white")
                elif cat_cols:
                    fig = px.bar(df.head(30), x=cat_cols[0], y=chart_metric,
                                 title=f"{chart_metric} by {cat_cols[0]}",
                                 template="plotly_white")
                else:
                    fig = px.histogram(df, x=chart_metric, template="plotly_white")
                st.plotly_chart(fig, use_container_width=True)

            st.subheader(f"Results ({len(df):,} rows)")
            st.dataframe(df, use_container_width=True, height=400)

            col_dl1, col_dl2 = st.columns(2)
            with col_dl1:
                st.download_button(
                    "⬇ Download CSV",
                    df.to_csv(index=False),
                    file_name=f"{cfg.database}_result.csv",
                    mime="text/csv",
                )
            with col_dl2:
                st.download_button(
                    "⬇ Download JSON",
                    df.to_json(orient="records", indent=2),
                    file_name=f"{cfg.database}_result.json",
                    mime="application/json",
                )
        else:
            st.warning("No rows returned." if success else f"Error: {er.get('error')}")

    with t_sql:
        sql = result.get("generated_sql", "")
        if sql:
            st.code(sql, language="sql")
            st.caption("The system automatically appends a LIMIT clause before execution.")

        if result.get("error_history"):
            st.subheader("Self-correction history")
            for i, err in enumerate(result["error_history"], 1):
                with st.expander(f"Attempt {i} — error"):
                    st.error(err)

    with t_debug:
        st.json({
            "provider":        info["provider"],
            "model":           info["model"],
            "database":        cfg.database,
            "db_type":         cfg.db_type,
            "collection":      collection_name,
            "question":        result.get("question"),
            "annotation":      result.get("annotation"),
            "retry_count":     result.get("retry_count"),
            "error_history":   result.get("error_history"),
            "schema_chars":    len(result.get("schema_context", "")),
        })
        with st.expander("Schema context sent to LLM"):
            st.code(result.get("schema_context", ""), language="sql")

# ── Query history ─────────────────────────────────────────────────────────────
history = st.session_state.user_query_history
if len(history) > 1:
    st.divider()
    st.subheader("📜 Recent queries")
    for h in history[1:6]:
        er   = h.get("execution_result") or {}
        icon = "✅" if er.get("success") else "❌"
        label = f"{icon} {h.get('question','')[:80]}  —  {h.get('timestamp','')}"
        with st.expander(label):
            st.code(h.get("generated_sql", ""), language="sql")
            if er.get("rows"):
                st.dataframe(
                    pd.DataFrame(er["rows"]).head(5),
                    use_container_width=True,
                )
