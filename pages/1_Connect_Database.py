"""
pages/1_Connect_Database.py
User-facing database connection page.

Step 1 — fill in connection form
Step 2 — test connection
Step 3 — index schema into ChromaDB
Step 4 — redirected to query page automatically
"""

from __future__ import annotations

import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Connect Database — SQL Agent Pro",
    page_icon="🔌",
    layout="wide",
)

from db.user_connection import (
    DB_DEFAULT_PORTS,
    DB_DRIVERS,
    DB_TYPES,
    UserConnectionConfig,
    build_user_schema_index,
    get_user_tables,
    test_user_connection,
)

# ── Init session state ────────────────────────────────────────────────────────
for k, v in {
    "user_config":        None,
    "user_collection":    None,
    "user_connected":     False,
    "user_tables":        [],
    "connection_tested":  False,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── Page header ───────────────────────────────────────────────────────────────
st.title("🔌 Connect your database")
st.caption("Enter your database credentials to start querying with the AI agent.")

if st.session_state.user_connected:
    cfg = st.session_state.user_config
    st.success(
        f"Already connected to **{cfg.database}** on `{cfg.host}` "
        f"({len(st.session_state.user_tables)} tables indexed)"
    )
    c1, c2 = st.columns([1, 5])
    with c1:
        if st.button("🔄 Change connection", use_container_width=True):
            st.session_state.user_connected  = False
            st.session_state.user_config     = None
            st.session_state.user_collection = None
            st.session_state.user_tables     = []
            st.rerun()
    with c2:
        if st.button("▶ Go to Query page →", type="primary", use_container_width=False):
            st.switch_page("pages/2_Query.py")
    st.divider()

st.subheader("1. Database type")
db_type = st.selectbox(
    "Choose your database",
    list(DB_TYPES.keys()),
    help="SQLite needs a file path only. All others need host/port/credentials.",
)

driver_note = DB_DRIVERS.get(db_type, "")
if driver_note != "(built-in)":
    st.info(f"Required driver: `pip install {driver_note}`", icon="ℹ️")

st.divider()
st.subheader("2. Connection details")

if db_type == "SQLite":
    sqlite_path = st.text_input(
        "SQLite file path",
        placeholder="/home/user/mydata.db",
        help="Absolute path to your .db or .sqlite file.",
    )
    host = port = database = username = password = schema = ""
    ssl = False
else:
    col1, col2 = st.columns([3, 1])
    with col1:
        host = st.text_input(
            "Host",
            placeholder="localhost  or  db.example.com  or  127.0.0.1",
        )
    with col2:
        port = st.number_input(
            "Port",
            value=DB_DEFAULT_PORTS.get(db_type, 5432),
            min_value=1,
            max_value=65535,
        )

    col3, col4 = st.columns(2)
    with col3:
        database = st.text_input("Database name", placeholder="mydb")
    with col4:
        schema = st.text_input(
            "Schema",
            value="public",
            placeholder="public",
            help="PostgreSQL schema. Leave as 'public' if unsure.",
        ) if db_type == "PostgreSQL" else "public"

    col5, col6 = st.columns(2)
    with col5:
        username = st.text_input("Username", placeholder="readonly_user")
    with col6:
        password = st.text_input("Password", type="password")

    ssl = st.checkbox(
        "Use SSL",
        value=False,
        help="Enable SSL/TLS for the connection (recommended for cloud databases).",
    ) if db_type == "PostgreSQL" else False

    sqlite_path = ""

# ── Quick presets ─────────────────────────────────────────────────────────────
with st.expander("Quick presets — cloud databases"):
    preset = st.selectbox(
        "Fill from preset",
        ["— select —", "Supabase", "Neon", "Amazon RDS", "Railway", "Render"],
        label_visibility="collapsed",
    )
    if preset == "Supabase":
        st.code("Host: db.<project-ref>.supabase.co\nPort: 5432\nDatabase: postgres\nUsername: postgres")
    elif preset == "Neon":
        st.code("Host: ep-<name>.<region>.aws.neon.tech\nPort: 5432\nDatabase: neondb")
    elif preset == "Amazon RDS":
        st.code("Host: <db>.xxxx.<region>.rds.amazonaws.com\nPort: 5432")
    elif preset == "Railway":
        st.caption("Copy the individual fields from your Railway service → Variables tab.")
    elif preset == "Render":
        st.caption("Copy from your Render PostgreSQL service → Info tab → External Database URL.")

st.divider()
st.subheader("3. Test & connect")

col_test, col_connect = st.columns([1, 1])

with col_test:
    if st.button("🔍 Test connection", use_container_width=True):
        if db_type == "SQLite" and not sqlite_path:
            st.error("Enter a SQLite file path.")
        elif db_type != "SQLite" and not all([host, database, username, password]):
            st.error("Fill in host, database, username, and password.")
        else:
            cfg = UserConnectionConfig(
                db_type=db_type,
                host=str(host),
                port=int(port) if port else 5432,
                database=str(database),
                username=str(username),
                password=str(password),
                schema=str(schema) if schema else "public",
                ssl=bool(ssl),
                sqlite_path=str(sqlite_path),
            )
            with st.spinner("Testing connection…"):
                ok, msg = test_user_connection(cfg)
            if ok:
                st.success(f"Connection successful! ✓")
                st.session_state.connection_tested = True
                st.session_state.user_config = cfg
            else:
                st.error(f"Connection failed: {msg}")
                st.session_state.connection_tested = False

with col_connect:
    btn_disabled = not st.session_state.connection_tested
    if st.button(
        "⚡ Connect & index schema",
        type="primary",
        use_container_width=True,
        disabled=btn_disabled,
        help="Test the connection first, then click here to index your schema.",
    ):
        cfg = st.session_state.user_config
        with st.spinner("Indexing your schema into ChromaDB…"):
            try:
                n_tables, collection_name = build_user_schema_index(cfg)
                tables = get_user_tables(cfg)
                st.session_state.user_connected  = True
                st.session_state.user_collection = collection_name
                st.session_state.user_tables     = tables
                st.success(f"Indexed {n_tables} tables. You're ready to query!")
                st.balloons()
            except Exception as exc:
                st.error(f"Schema indexing failed: {exc}")

# ── Show indexed tables if connected ─────────────────────────────────────────
if st.session_state.user_connected and st.session_state.user_tables:
    st.divider()
    st.subheader("Indexed tables")
    cols = st.columns(4)
    for i, table in enumerate(st.session_state.user_tables):
        cols[i % 4].code(table, language=None)

    st.divider()
    st.success("Schema indexed. Head to the **Query** page to start asking questions.")
    if st.button("▶ Go to Query →", type="primary"):
        st.switch_page("pages/2_Query.py")
