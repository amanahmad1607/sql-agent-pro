"""
app.py — SQL Agent Pro
Dark industrial UI: Syne + Space Mono + JetBrains Mono typography,
indigo/emerald accent palette, animated pipeline tracker,
glowing metric cards, dark Plotly charts.
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

from utils.observability import configure as configure_logging
configure_logging()

st.set_page_config(
    page_title="SQL Agent Pro",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"] { font-family:'Syne',sans-serif !important; }

/* Background */
.stApp {
    background:#080810;
    background-image:
        radial-gradient(ellipse at 15% 0%,   rgba(99,102,241,.09) 0%,transparent 55%),
        radial-gradient(ellipse at 85% 100%,  rgba(16,185,129,.06) 0%,transparent 55%);
}

/* Sidebar */
[data-testid="stSidebar"] {
    background:#0b0b15 !important;
    border-right:1px solid rgba(99,102,241,.14) !important;
}
[data-testid="stSidebar"] * { color:#c4c4d4 !important; }

/* Typography */
h1,h2,h3 { font-family:'Syne',sans-serif !important; color:#fff !important; letter-spacing:-.5px; }

/* Hero */
.hero {
    background:linear-gradient(135deg,#0c0c18 0%,#0f0f1e 100%);
    border:1px solid rgba(99,102,241,.2);
    border-radius:18px;
    padding:34px 38px;
    margin-bottom:22px;
    position:relative;
    overflow:hidden;
}
.hero::before {
    content:'';position:absolute;top:-80px;right:-80px;
    width:260px;height:260px;
    background:radial-gradient(circle,rgba(99,102,241,.14) 0%,transparent 70%);
    border-radius:50%;pointer-events:none;
}
.hero::after {
    content:'';position:absolute;bottom:-50px;left:-50px;
    width:180px;height:180px;
    background:radial-gradient(circle,rgba(16,185,129,.09) 0%,transparent 70%);
    border-radius:50%;pointer-events:none;
}
.hero-title {
    font-family:'Syne',sans-serif;
    font-size:2.55rem;font-weight:800;color:#fff;
    line-height:1.08;margin:0 0 10px 0;letter-spacing:-1.2px;
}
.hero-title span {
    background:linear-gradient(135deg,#6366f1,#10b981);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}
.hero-sub {
    font-family:'Space Mono',monospace;
    font-size:.72rem;color:#4b4b6a;letter-spacing:.8px;margin:0;
}

/* Pills */
.pill {
    display:inline-block;padding:3px 10px;border-radius:20px;
    font-family:'Space Mono',monospace;font-size:.65rem;font-weight:700;
    letter-spacing:.4px;margin-right:5px;
}
.pg { background:rgba(16,185,129,.14); color:#10b981; border:1px solid rgba(16,185,129,.28); }
.po { background:rgba(99,102,241,.14); color:#818cf8; border:1px solid rgba(99,102,241,.28); }
.pa { background:rgba(245,158,11,.14); color:#f59e0b; border:1px solid rgba(245,158,11,.28); }
.pz { background:rgba(148,163,184,.1); color:#94a3b8; border:1px solid rgba(148,163,184,.2); }

/* Nav cards */
.ncard {
    background:#0d0d1a;
    border:1px solid rgba(99,102,241,.17);
    border-radius:13px;padding:20px 22px;
    transition:border-color .2s,transform .2s;
}
.ncard:hover { border-color:rgba(99,102,241,.42);transform:translateY(-2px); }
.ncard-icon  { font-size:1.4rem;margin-bottom:8px; }
.ncard-title { font-family:'Syne',sans-serif;font-size:.93rem;font-weight:700;color:#e0e0f0;margin:0 0 4px; }
.ncard-desc  { font-size:.76rem;color:#6b6b8a;margin:0;line-height:1.5; }

/* Section label */
.slabel {
    font-family:'Space Mono',monospace;font-size:.65rem;
    color:#6366f1;letter-spacing:2px;text-transform:uppercase;
    margin:20px 0 9px;
}

/* Textarea */
.stTextArea textarea {
    background:#111120 !important;
    border:1px solid rgba(99,102,241,.22) !important;
    border-radius:11px !important;
    color:#e2e2f0 !important;
    font-family:'JetBrains Mono',monospace !important;
    font-size:.87rem !important;resize:none !important;
}
.stTextArea textarea:focus {
    border-color:rgba(99,102,241,.55) !important;
    box-shadow:0 0 0 3px rgba(99,102,241,.1) !important;
}

/* Selectbox */
.stSelectbox > div > div {
    background:#111120 !important;
    border-color:rgba(99,102,241,.2) !important;
    color:#c4c4d4 !important;border-radius:11px !important;
}

/* Primary button */
.stButton > button[kind="primary"] {
    background:linear-gradient(135deg,#6366f1,#4f46e5) !important;
    border:none !important;border-radius:10px !important;color:#fff !important;
    font-family:'Syne',sans-serif !important;font-weight:700 !important;
    font-size:.87rem !important;letter-spacing:.2px !important;
    box-shadow:0 4px 18px rgba(99,102,241,.32) !important;
    transition:opacity .18s,transform .15s,box-shadow .15s !important;
}
.stButton > button[kind="primary"]:hover {
    opacity:.9 !important;transform:translateY(-1px) !important;
    box-shadow:0 6px 24px rgba(99,102,241,.42) !important;
}
/* Secondary button */
.stButton > button:not([kind="primary"]) {
    background:transparent !important;
    border:1px solid rgba(99,102,241,.22) !important;
    border-radius:10px !important;color:#8b8ba7 !important;
    font-family:'Syne',sans-serif !important;font-weight:600 !important;
    font-size:.83rem !important;transition:border-color .18s,color .18s !important;
}
.stButton > button:not([kind="primary"]):hover {
    border-color:rgba(99,102,241,.5) !important;color:#c4c4f4 !important;
}

/* Metric cards */
.mrow { display:flex;gap:12px;margin:20px 0;flex-wrap:wrap; }
.mc {
    flex:1;min-width:110px;background:#0d0d1a;
    border-radius:13px;padding:16px 18px;
    position:relative;overflow:hidden;
}
.mc.ms { border:1px solid rgba(16,185,129,.28); }
.mc.mn { border:1px solid rgba(99,102,241,.18); }
.mc.mw { border:1px solid rgba(245,158,11,.22); }
.mc.mf { border:1px solid rgba(239,68,68,.28); }
.mc::before { content:'';position:absolute;top:0;left:0;right:0;height:2px; }
.mc.ms::before { background:linear-gradient(90deg,#10b981,#059669); }
.mc.mn::before { background:linear-gradient(90deg,#6366f1,#4f46e5); }
.mc.mw::before { background:linear-gradient(90deg,#f59e0b,#d97706); }
.mc.mf::before { background:linear-gradient(90deg,#ef4444,#dc2626); }
.ml { font-family:'Space Mono',monospace;font-size:.62rem;letter-spacing:1.5px;
      text-transform:uppercase;color:#6b6b8a;margin-bottom:6px; }
.mv { font-family:'Syne',sans-serif;font-size:1.48rem;font-weight:800;color:#fff;line-height:1; }
.ms2 { font-family:'Space Mono',monospace;font-size:.62rem;color:#6b6b8a;margin-top:4px; }

/* Pipeline */
.pipe { display:flex;align-items:center;gap:4px;margin:14px 0;flex-wrap:wrap; }
.ps {
    display:flex;align-items:center;gap:5px;
    padding:5px 11px;border-radius:20px;
    font-family:'Space Mono',monospace;font-size:.65rem;font-weight:700;
}
.pd { background:rgba(16,185,129,.12);color:#10b981;border:1px solid rgba(16,185,129,.24); }
.pa2 { background:rgba(99,102,241,.14);color:#818cf8;border:1px solid rgba(99,102,241,.32);
       animation:puls 1.6s ease-in-out infinite; }
.pi { background:rgba(255,255,255,.03);color:#3b3b5a;border:1px solid rgba(255,255,255,.05); }
.parr { color:#2b2b4a;font-size:.68rem; }
@keyframes puls {
    0%,100% { box-shadow:0 0 0 0 rgba(99,102,241,0); }
    50%      { box-shadow:0 0 0 5px rgba(99,102,241,.18); }
}

/* Answer */
.ans-wrap {
    background:linear-gradient(135deg,#0b0f14,#0d1018);
    border:1px solid rgba(16,185,129,.22);
    border-left:3px solid #10b981;
    border-radius:13px;padding:20px 22px;margin:8px 0;
}
.ans-label {
    font-family:'Space Mono',monospace;font-size:.62rem;
    color:#10b981;letter-spacing:2px;text-transform:uppercase;margin-bottom:10px;
}
.ans-text { font-family:'Syne',sans-serif;font-size:.98rem;color:#d0d0e8;line-height:1.72;margin:0; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background:#0d0d1a !important;border-radius:11px !important;
    padding:4px !important;gap:2px !important;
    border:1px solid rgba(99,102,241,.12) !important;
}
.stTabs [data-baseweb="tab"] {
    background:transparent !important;border-radius:8px !important;
    color:#6b6b8a !important;font-family:'Syne',sans-serif !important;
    font-weight:600 !important;font-size:.81rem !important;
    padding:8px 16px !important;transition:all .18s !important;
}
.stTabs [aria-selected="true"] {
    background:rgba(99,102,241,.18) !important;color:#a5b4fc !important;
}

/* Dataframe */
.stDataFrame { border-radius:12px !important;overflow:hidden !important;
               border:1px solid rgba(99,102,241,.13) !important; }

/* Code */
.stCode,[data-testid="stCode"] {
    background:#0d0d1a !important;
    border:1px solid rgba(99,102,241,.13) !important;border-radius:10px !important;
}

/* Expander */
[data-testid="stExpander"] {
    background:#0d0d1a !important;border:1px solid rgba(99,102,241,.12) !important;
    border-radius:10px !important;
}
[data-testid="stExpander"] summary {
    font-family:'Space Mono',monospace !important;font-size:.76rem !important;color:#8b8ba7 !important;
}

/* Sidebar metric rows */
.sbm {
    background:#12121f;border-radius:8px;padding:9px 13px;margin:3px 0;
    border:1px solid rgba(99,102,241,.09);
    display:flex;justify-content:space-between;align-items:center;
}
.sbl { font-family:'Space Mono',monospace;font-size:.65rem;color:#6b6b8a; }
.sbv { font-family:'Syne',sans-serif;font-size:.8rem;font-weight:700;color:#a5b4fc; }

/* Download */
.stDownloadButton > button {
    background:transparent !important;
    border:1px solid rgba(16,185,129,.28) !important;border-radius:8px !important;
    color:#10b981 !important;font-family:'Space Mono',monospace !important;
    font-size:.68rem !important;font-weight:700 !important;letter-spacing:.4px !important;
    padding:6px 13px !important;transition:background .18s !important;
}
.stDownloadButton > button:hover { background:rgba(16,185,129,.1) !important; }

/* Spinner */
.stSpinner > div { border-top-color:#6366f1 !important; }

/* Scrollbar */
::-webkit-scrollbar{width:5px;}
::-webkit-scrollbar-track{background:#080810;}
::-webkit-scrollbar-thumb{background:rgba(99,102,241,.28);border-radius:3px;}

/* Dividers */
hr { border-color:rgba(99,102,241,.1) !important; }

/* Hide Streamlit chrome */
#MainMenu,footer,header { visibility:hidden; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────
for k, v in {"history": [], "last_result": None, "schema_built": False}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def cached_run_agent(question: str) -> dict:
    from agents.graph import run_agent
    return run_agent(question)


@st.cache_data(ttl=3600, show_spinner=False)
def get_indexed_tables() -> list[str]:
    try:
        from db.schema_vector import _get_chroma_client, _get_collection
        client = _get_chroma_client()
        col    = _get_collection(client)
        result = col.get(include=["metadatas"])
        return sorted(m["table_name"] for m in (result["metadatas"] or []))
    except Exception:
        return []


def try_build_schema():
    if not st.session_state.schema_built:
        try:
            from db.schema_vector import build_schema_index
            build_schema_index(schema=os.getenv("DB_SCHEMA", "public"))
            st.session_state.schema_built = True
        except Exception:
            pass


def dark_chart(fig, title="", height=340):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#0d0d1a",
        font=dict(family="Syne", color="#c4c4d4"),
        title=dict(text=title, font=dict(family="Syne", size=13, color="#e0e0f0")),
        xaxis=dict(gridcolor="rgba(99,102,241,.07)", linecolor="rgba(99,102,241,.13)",
                   tickfont=dict(family="Space Mono", size=9, color="#6b6b8a")),
        yaxis=dict(gridcolor="rgba(99,102,241,.07)", linecolor="rgba(99,102,241,.13)",
                   tickfont=dict(family="Space Mono", size=9, color="#6b6b8a")),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(family="Syne", color="#8b8ba7")),
        margin=dict(l=8, r=8, t=36, b=8),
        height=height,
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# PROVIDER
# ─────────────────────────────────────────────────────────────────────────────
from agents.llm import get_provider_info
info  = get_provider_info()
prov  = info["provider"]
model = info["model"]
pcls  = {"groq": "pg", "openai": "po", "anthropic": "pa"}.get(prov, "pz")

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
    <div style='padding:4px 0 18px'>
      <div style='font-family:Syne,sans-serif;font-size:1.12rem;font-weight:800;
                  color:#fff;letter-spacing:-.5px;margin-bottom:3px'>⚡ SQL Agent Pro</div>
      <div style='font-family:Space Mono,monospace;font-size:.6rem;
                  color:#4b4b6a;letter-spacing:1px'>AGENTIC TEXT-TO-SQL</div>
    </div>

    <div style='background:#12121f;border:1px solid rgba(99,102,241,.14);
                border-radius:10px;padding:12px 14px;margin-bottom:14px'>
      <div style='font-family:Space Mono,monospace;font-size:.58rem;color:#6b6b8a;
                  letter-spacing:1.5px;text-transform:uppercase;margin-bottom:8px'>
        Active Provider
      </div>
      <span class='pill {pcls}'>{prov.upper()}</span>
      <div style='font-family:JetBrains Mono,monospace;font-size:.68rem;
                  color:#8b8ba7;margin-top:8px;word-break:break-all'>{model}</div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔌 Test DB", use_container_width=True):
            try:
                from db.connector import health_check
                health_check()
                st.success("Connected ✓")
            except Exception as e:
                st.error(str(e)[:80])
    with c2:
        if st.button("🗂 Re-index", use_container_width=True):
            with st.spinner("Indexing…"):
                try:
                    from db.schema_vector import build_schema_index
                    n = build_schema_index(
                        schema=os.getenv("DB_SCHEMA", "public"), force_rebuild=True
                    )
                    st.success(f"{n} tables")
                    get_indexed_tables.clear()
                    st.session_state.schema_built = True
                except Exception as e:
                    st.error(str(e)[:80])

    st.markdown("""<div style='font-family:Space Mono,monospace;font-size:.6rem;color:#6b6b8a;
        letter-spacing:1.5px;text-transform:uppercase;margin:14px 0 7px'>
        Indexed Tables</div>""", unsafe_allow_html=True)

    tables = get_indexed_tables()
    if tables:
        for t in tables:
            st.markdown(f"""
            <div style='font-family:JetBrains Mono,monospace;font-size:.7rem;color:#8b8ba7;
                        background:#12121f;border:1px solid rgba(99,102,241,.09);
                        border-radius:6px;padding:5px 10px;margin:2px 0'>{t}</div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("<div style='font-family:Space Mono,monospace;font-size:.68rem;"
                    "color:#3b3b5a'>None — click Re-index</div>", unsafe_allow_html=True)

    st.markdown("""<div style='font-family:Space Mono,monospace;font-size:.6rem;color:#6b6b8a;
        letter-spacing:1.5px;text-transform:uppercase;margin:16px 0 7px'>
        Guardrails</div>""", unsafe_allow_html=True)

    for lbl, val in [
        ("Max rows",    os.getenv("MAX_ROWS", 1000)),
        ("Max retries", os.getenv("MAX_RETRIES", 3)),
        ("PII masking", "ON" if os.getenv("ENABLE_PII_MASKING") == "true" else "OFF"),
        ("Retry delay", f"{os.getenv('GROQ_RETRY_DELAY', 1.0)}s"),
    ]:
        st.markdown(f"""<div class='sbm'>
          <span class='sbl'>{lbl}</span>
          <span class='sbv'>{val}</span>
        </div>""", unsafe_allow_html=True)

    st.markdown("""<div style='margin-top:22px;font-family:Space Mono,monospace;
        font-size:.58rem;color:#2b2b42;text-align:center'>
        SQL AGENT PRO · v2.0.0</div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
try_build_schema()

# Hero
st.markdown(f"""
<div class='hero'>
  <div style='display:flex;align-items:flex-start;
              justify-content:space-between;flex-wrap:wrap;gap:14px'>
    <div>
      <h1 class='hero-title'>Query your data<br>in <span>plain English</span></h1>
      <p class='hero-sub'>LANGGRAPH · CHROMADB · {prov.upper()} / {model}</p>
    </div>
    <div style='text-align:right'>
      <span class='pill {pcls}'>{prov.upper()}</span>
      <div style='font-family:Space Mono,monospace;font-size:.6rem;
                  color:#3b3b5a;margin-top:6px'>{model}</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# Nav cards
nc1, nc2 = st.columns(2)
with nc1:
    st.markdown("""<div class='ncard'>
      <div class='ncard-icon'>🔌</div>
      <div class='ncard-title'>Connect your database</div>
      <div class='ncard-desc'>PostgreSQL · MySQL · SQLite · SQL Server —
        connect any database and start querying instantly.</div>
    </div>""", unsafe_allow_html=True)
    if st.button("Connect a database →", use_container_width=True):
        st.switch_page("pages/1_Connect_Database.py")

with nc2:
    st.markdown("""<div class='ncard'>
      <div class='ncard-icon'>📊</div>
      <div class='ncard-title'>Demo database</div>
      <div class='ncard-desc'>Built-in schema with customers, orders, products,
        and support tickets — explore below.</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

# ── Query input ───────────────────────────────────────────────────────────────
EXAMPLES = [
    "Top 10 customers by total order value",
    "Month-over-month revenue growth this year",
    "Products with the highest return rate",
    "Orders pending more than 7 days",
    "Average order value by customer segment",
    "Support tickets by priority and status",
]

st.markdown("<div class='slabel'>Ask a question</div>", unsafe_allow_html=True)

example = st.selectbox(
    "Examples",
    ["— pick an example or type below —"] + EXAMPLES,
    label_visibility="collapsed",
)

question = st.text_area(
    "Question",
    value="" if example.startswith("—") else example,
    height=88,
    placeholder="e.g.  Which customers placed orders last month but not this month?",
    label_visibility="collapsed",
)

c1, c2, _ = st.columns([2, 1, 5])
with c1:
    run = st.button("⚡ Run Query", type="primary", use_container_width=True)
with c2:
    if st.button("✕ Clear", use_container_width=True):
        st.session_state.history     = []
        st.session_state.last_result = None
        cached_run_agent.clear()
        st.rerun()

# ── Execute ───────────────────────────────────────────────────────────────────
if run and question.strip():
    pipe_ph = st.empty()
    pipe_ph.markdown("""<div class='pipe'>
      <div class='ps pa2'>● ANNOTATE</div><div class='parr'>›</div>
      <div class='ps pi'>GENERATE</div><div class='parr'>›</div>
      <div class='ps pi'>EXECUTE</div><div class='parr'>›</div>
      <div class='ps pi'>CHECK</div><div class='parr'>›</div>
      <div class='ps pi'>FORMAT</div>
    </div>""", unsafe_allow_html=True)

    with st.spinner(""):
        t0 = time.time()
        try:
            result = cached_run_agent(question.strip())
            result["elapsed"]   = round(time.time() - t0, 2)
            result["timestamp"] = datetime.now().strftime("%H:%M:%S")
            st.session_state.last_result = result
            st.session_state.history.insert(0, result)

            er  = result.get("execution_result") or {}
            ok  = er.get("success", False)
            end = "pd" if ok else "ps pi"
            pipe_ph.markdown(f"""<div class='pipe'>
              <div class='ps pd'>✓ ANNOTATE</div><div class='parr'>›</div>
              <div class='ps pd'>✓ GENERATE</div><div class='parr'>›</div>
              <div class='ps pd'>✓ EXECUTE</div><div class='parr'>›</div>
              <div class='ps pd'>✓ CHECK</div><div class='parr'>›</div>
              <div class='ps {end}'>{'✓' if ok else '✗'} FORMAT</div>
            </div>""", unsafe_allow_html=True)
        except Exception as exc:
            pipe_ph.empty()
            st.error(f"Agent error: {exc}")

# ── Results ───────────────────────────────────────────────────────────────────
result = st.session_state.last_result
if result:
    er      = result.get("execution_result") or {}
    success = er.get("success", False)
    elapsed = result.get("elapsed", 0)
    retries = result.get("retry_count", 0)
    nrows   = er.get("row_count", 0)

    scls = "ms" if success else "mf"
    rcls = "mw" if retries > 0 else "mn"

    st.markdown(f"""
    <div class='mrow'>
      <div class='mc {scls}'>
        <div class='ml'>Status</div>
        <div class='mv'>{'OK' if success else 'FAIL'}</div>
        <div class='ms2'>{'query succeeded' if success else 'query failed'}</div>
      </div>
      <div class='mc mn'>
        <div class='ml'>Rows</div>
        <div class='mv'>{nrows:,}</div>
        <div class='ms2'>max {os.getenv('MAX_ROWS',1000)}</div>
      </div>
      <div class='mc {rcls}'>
        <div class='ml'>Retries</div>
        <div class='mv'>{retries}</div>
        <div class='ms2'>of {os.getenv('MAX_RETRIES',3)} max</div>
      </div>
      <div class='mc mn'>
        <div class='ml'>Elapsed</div>
        <div class='mv'>{elapsed}s</div>
        <div class='ms2'>end-to-end</div>
      </div>
    </div>""", unsafe_allow_html=True)

    t_ans, t_data, t_sql, t_debug = st.tabs(
        ["💡  Answer", "📊  Data & Chart", "🔧  SQL", "🔬  Debug"]
    )

    with t_ans:
        answer = result.get("final_answer") or "No answer generated."
        st.markdown(f"""
        <div class='ans-wrap'>
          <div class='ans-label'>AI Insight</div>
          <p class='ans-text'>{answer}</p>
        </div>""", unsafe_allow_html=True)

    with t_data:
        data_rows = er.get("rows", [])
        if data_rows:
            df       = pd.DataFrame(data_rows)
            num_cols = df.select_dtypes("number").columns.tolist()
            date_cols= [c for c in df.columns if any(
                k in c.lower() for k in ("date","month","year","week","day","time"))]
            cat_cols = df.select_dtypes("object").columns.tolist()

            palette = ["#6366f1","#10b981","#f59e0b","#ec4899","#3b82f6","#8b5cf6","#06b6d4"]

            if num_cols:
                st.markdown("<div class='slabel'>Auto Chart</div>", unsafe_allow_html=True)
                col_m, col_t = st.columns([2, 2])
                with col_m:
                    metric = st.selectbox("Metric", num_cols,
                                          key="cm", label_visibility="collapsed")
                with col_t:
                    ctype = st.selectbox("Type",
                        ["Auto","Bar","Line","Area","Scatter","Histogram"],
                        key="ct", label_visibility="collapsed")

                if ctype == "Auto":
                    ctype = "Line" if date_cols else ("Bar" if cat_cols else "Histogram")

                if ctype == "Bar" and cat_cols:
                    fig = px.bar(df.head(30), x=cat_cols[0], y=metric,
                                 color_discrete_sequence=palette)
                elif ctype == "Line":
                    xc = date_cols[0] if date_cols else (cat_cols[0] if cat_cols else metric)
                    fig = px.line(df, x=xc, y=metric, markers=True,
                                  color_discrete_sequence=palette)
                    fig.update_traces(line_width=2.5,
                                      marker=dict(size=6, line=dict(width=1.5, color="#080810")))
                elif ctype == "Area":
                    xc = date_cols[0] if date_cols else (cat_cols[0] if cat_cols else metric)
                    fig = px.area(df, x=xc, y=metric, color_discrete_sequence=palette)
                    fig.update_traces(line_width=2)
                elif ctype == "Scatter" and len(num_cols) >= 2:
                    y2 = next((c for c in num_cols if c != metric), num_cols[0])
                    fig = px.scatter(df, x=metric, y=y2, color_discrete_sequence=palette)
                    fig.update_traces(marker_size=8)
                else:
                    fig = px.histogram(df, x=metric, color_discrete_sequence=palette)

                st.plotly_chart(dark_chart(fig, f"{metric} analysis"),
                                use_container_width=True,
                                config={"displayModeBar": False})

            st.markdown(f"<div class='slabel'>Result Table — {len(df):,} rows</div>",
                        unsafe_allow_html=True)
            st.dataframe(df, use_container_width=True,
                         height=min(420, 56 + len(df) * 36))

            dl1, dl2 = st.columns(2)
            with dl1:
                st.download_button("⬇  CSV", df.to_csv(index=False),
                                   "result.csv", "text/csv")
            with dl2:
                st.download_button("⬇  JSON",
                                   df.to_json(orient="records", indent=2),
                                   "result.json", "application/json")
        else:
            msg = er.get("error", "No rows returned.")
            st.markdown(f"""
            <div style='background:#110d0d;border:1px solid rgba(239,68,68,.22);
                        border-left:3px solid #ef4444;border-radius:12px;
                        padding:18px 20px;font-family:Space Mono,monospace;
                        font-size:.78rem;color:#f87171'>{msg}</div>
            """, unsafe_allow_html=True)

    with t_sql:
        sql = result.get("generated_sql", "")
        if sql:
            st.markdown("<div class='slabel'>Generated SQL</div>", unsafe_allow_html=True)
            st.code(sql, language="sql")
            st.markdown("""<div style='font-family:Space Mono,monospace;font-size:.62rem;
                color:#3b3b5a;margin-top:5px'>
                ↳ wrapped in SELECT * FROM (…) AS __limited__ LIMIT 1000 before execution
                </div>""", unsafe_allow_html=True)

        if result.get("error_history"):
            st.markdown("<div class='slabel' style='color:#f59e0b;margin-top:16px'>"
                        "Self-Correction History</div>", unsafe_allow_html=True)
            for i, err in enumerate(result["error_history"], 1):
                with st.expander(f"Attempt {i} — error"):
                    st.markdown(f"""<div style='font-family:JetBrains Mono,monospace;
                        font-size:.76rem;color:#f87171;padding:4px 0'>{err}</div>
                    """, unsafe_allow_html=True)

    with t_debug:
        st.markdown("<div class='slabel'>Agent State</div>", unsafe_allow_html=True)
        st.json({
            "provider":      prov,
            "model":         model,
            "question":      result.get("question"),
            "annotation":    result.get("annotation"),
            "retry_count":   result.get("retry_count"),
            "error_history": result.get("error_history"),
            "schema_chars":  len(result.get("schema_context", "")),
        })
        with st.expander("Schema context sent to LLM"):
            st.code(result.get("schema_context", ""), language="sql")


# ── History ───────────────────────────────────────────────────────────────────
history = st.session_state.history
if len(history) > 1:
    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    st.markdown("<div class='slabel'>Recent Queries</div>", unsafe_allow_html=True)
    for h in history[1:6]:
        er   = h.get("execution_result") or {}
        ok   = er.get("success", False)
        icon = "✓" if ok else "✗"
        q    = h.get("question", "")[:88]
        t    = h.get("timestamp", "")
        with st.expander(f"{icon}  {q}"):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.code(h.get("generated_sql", ""), language="sql")
            with c2:
                st.markdown(f"""
                <div style='font-family:Space Mono,monospace;font-size:.62rem;color:#6b6b8a;
                            line-height:1.9'>
                  <div>{t}</div>
                  <div>{er.get('row_count',0):,} rows</div>
                  <div>{h.get('retry_count',0)} retries</div>
                  <div>{h.get('elapsed','—')}s</div>
                </div>""", unsafe_allow_html=True)
            if er.get("rows"):
                st.dataframe(pd.DataFrame(er["rows"]).head(5), use_container_width=True)