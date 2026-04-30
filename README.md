# SQL Agent Pro ⚡

> **Production-grade Agentic Text-to-SQL** powered by **Groq + Llama 3.3 70B**,
> LangGraph self-correction, ChromaDB semantic schema retrieval, and a dark industrial Streamlit UI.

---

## What it does

You type a question in plain English. The agent:

1. Retrieves the 5 most relevant tables from ChromaDB (semantic search, not brute-force DDL dump)
2. Sends schema context + few-shot examples to Groq's Llama 3.3 70B
3. Generates a PostgreSQL SELECT query
4. Validates it through a 4-layer security pipeline
5. Executes it against your database (read-only enforced at engine level)
6. If it fails, feeds the error back to the LLM and retries up to 3 times
7. Summarises the result in natural language with an auto-generated chart

---

## Architecture

```
User Question
      │
      ▼
┌─────────────────────────────────────────────────────────┐
│                   LangGraph Agent                        │
│                                                          │
│  annotate_query  ──►  generate_sql  ◄──────────────┐    │
│  (ChromaDB              (Groq /                     │    │
│   top-5 tables)          Llama 3.3 70B)             │    │
│                               │                     │    │
│                          execute_sql            increment │
│                          (guardrails +           _retry   │
│                           SQLAlchemy)                │    │
│                               │                     │    │
│                          check_result ──────────────┘    │
│                               │ success                   │
│                          format_answer                    │
│                          (Groq summary)                   │
└─────────────────────────────────────────────────────────┘
      │
      ▼
Streamlit UI  →  Answer + Chart + SQL + Debug
```

---

## Project Structure

```
sql-agent-pro/
│
├── agents/
│   ├── llm.py                  # LLM factory — Groq default, swap via env
│   ├── graph.py                # LangGraph state machine (main DB)
│   ├── user_graph.py           # LangGraph state machine (user-connected DB)
│   ├── tools.py                # @tool: retrieve_schema, execute_sql
│   ├── prompts.py              # All prompt templates (tuned for Llama 3.3 70B)
│   └── metadata_extractor.py   # Unstructured text column intelligence
│
├── db/
│   ├── connector.py            # SQLAlchemy QueuePool, read-only enforcement
│   ├── schema_vector.py        # ChromaDB indexing + semantic retrieval
│   ├── user_connection.py      # Dynamic per-user DB connection manager
│   └── init.sql                # Demo schema + read-only PostgreSQL user
│
├── utils/
│   ├── guardrails.py           # 4-layer SQL security pipeline
│   └── observability.py        # structlog + LangSmith tracing
│
├── pages/
│   ├── 1_Connect_Database.py   # User DB connection UI (3-step flow)
│   └── 2_Query.py              # Query UI for user-connected databases
│
├── tests/
│   ├── test_guardrails.py      # 11 security tests — no credentials needed
│   └── test_agent_integration.py  # 15 integration tests — fully mocked
│
├── app.py                      # Main Streamlit UI (dark industrial theme)
├── cli.py                      # Operator CLI
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
└── .env.example
```

---

## Quick Start

### 1. Get a Groq API key (free)

[https://console.groq.com](https://console.groq.com) → API Keys → Create key

### 2. Clone and configure

```bash
git clone https://github.com/amanahmad1607/sql-agent-pro
cd sql-agent-pro
cp .env.example .env
```

Minimum `.env` to get started:

```bash
GROQ_API_KEY=gsk_...
DB_HOST=localhost
DB_PORT=5432
DB_NAME=your_database
DB_USER=sql_agent_readonly
DB_PASSWORD=your_password
```

### 3. Install

```bash
python3.11 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Start PostgreSQL (Docker)

```bash
docker-compose up postgres -d
```

### 5. Setup read-only user (skip if using Docker — init.sql does this)

```sql
CREATE ROLE sql_agent_readonly LOGIN PASSWORD 'your_password';
GRANT CONNECT ON DATABASE yourdb TO sql_agent_readonly;
GRANT USAGE ON SCHEMA public TO sql_agent_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO sql_agent_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO sql_agent_readonly;
```

### 6. Verify + index + run

```bash
python cli.py health-check       # check DB and ChromaDB
python cli.py index-schema       # build semantic schema index
python cli.py run-query -q "Top 5 customers by revenue"  # terminal test
streamlit run app.py             # launch UI → http://localhost:8501
```

---

## Switching LLM Provider

Change two lines in `.env` — zero code changes required:

```bash
# Groq (default — fastest)
LLM_PROVIDER=groq
LLM_MODEL=llama-3.3-70b-versatile
GROQ_API_KEY=gsk_...

# OpenAI
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
OPENAI_API_KEY=sk-...

# Anthropic
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3-5-sonnet-20241022
ANTHROPIC_API_KEY=sk-ant-...
```

### Groq Model Options

| Model                       | Speed     | Best for                           |
| --------------------------- | --------- | ---------------------------------- |
| `llama-3.3-70b-versatile` | Fast      | SQL generation —**default** |
| `llama3-70b-8192`         | Fast      | Long schema contexts               |
| `mixtral-8x7b-32768`      | Very fast | Simpler queries                    |
| `llama3-8b-8192`          | Blazing   | Dev and testing                    |

---

## Connecting Your Own Database

### Via UI

1. Open the app → click **"Connect a database →"**
2. Fill in your credentials (host, port, database, username, password)
3. Click **Test connection**
4. Click **Connect & index schema**
5. Go to the Query page and start asking questions

### Supported databases

| Database   | Driver installed        | Notes                            |
| ---------- | ----------------------- | -------------------------------- |
| PostgreSQL | `psycopg2-binary` ✓  | Full support, read-only enforced |
| MySQL      | `pip install pymysql` | Uncomment in requirements.txt    |
| SQLite     | Built-in ✓             | File path only, no credentials   |
| SQL Server | `pip install pyodbc`  | Requires ODBC Driver 17          |

### Cloud databases (fill `.env` with these values)

**Supabase:**

```
DB_HOST=db.<project-ref>.supabase.co
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
```

**Neon:**

```
DB_HOST=ep-<name>.<region>.aws.neon.tech
DB_PORT=5432
DB_NAME=neondb
```

**Amazon RDS:**

```
DB_HOST=<instance>.<id>.<region>.rds.amazonaws.com
DB_PORT=5432
```

---

## Security Architecture

```
SQL Input
    │
    ▼  Layer 1: sqlglot AST parse
       • Rejects all non-SELECT statement types
       • Catches mutations embedded inside CTEs
    │
    ▼  Layer 2: Regex keyword fallback
       • Blocks: DROP, DELETE, UPDATE, INSERT, CREATE,
         ALTER, TRUNCATE, EXEC, GRANT, REVOKE
    │
    ▼  Layer 3: Automatic LIMIT injection
       • Wraps: SELECT * FROM (...) AS __limited__ LIMIT 1000
       • Cannot be bypassed by the LLM
    │
    ▼  Layer 4: Presidio PII masking  [optional]
       • Masks emails, SSNs, names in results
       • Activate: ENABLE_PII_MASKING=true
```

**Database level:** `set_session(readonly=True)` on every SQLAlchemy connection + 30s statement timeout.

---

## Self-Correction Loop

```
generate_sql  (attempt 1)
      │
      ▼
 execute_sql ──► success ──► format_answer ──► END
      │
      │ error
      ▼
 increment_retry
 (appends error message to history)
      │
      ▼
 generate_sql  (attempt 2 — receives error as context)
      │
      └── repeats up to MAX_RETRIES=3
```

On Groq, the retry delay is controlled by `GROQ_RETRY_DELAY=1.0` (seconds).
Raise to `2.0` if you hit 429 rate limit errors on the free tier.

---

## CLI Reference

```bash
# Check database and ChromaDB connectivity
python cli.py health-check

# Build schema index (first-time or after schema changes)
python cli.py index-schema
python cli.py index-schema --schema myschema
python cli.py index-schema --force          # full rebuild

# Run a query from the terminal
python cli.py run-query -q "Top 10 products by revenue"
python cli.py run-query -q "..." -o result.json   # save full output

# Export introspected schema as JSON
python cli.py export-schema -o schema.json
```

---

## Configuration Reference

| Variable                 | Default                     | Description                                                 |
| ------------------------ | --------------------------- | ----------------------------------------------------------- |
| `GROQ_API_KEY`         | —                          | Groq API key (required if LLM_PROVIDER=groq)                |
| `OPENAI_API_KEY`       | —                          | OpenAI API key (if LLM_PROVIDER=openai)                     |
| `ANTHROPIC_API_KEY`    | —                          | Anthropic API key (if LLM_PROVIDER=anthropic)               |
| `LLM_PROVIDER`         | `groq`                    | `groq`, `openai`, or `anthropic`                      |
| `LLM_MODEL`            | `llama-3.3-70b-versatile` | Model name for the selected provider                        |
| `DB_HOST`              | `localhost`               | PostgreSQL host                                             |
| `DB_PORT`              | `5432`                    | PostgreSQL port                                             |
| `DB_NAME`              | —                          | Database name                                               |
| `DB_USER`              | —                          | Database username (use read-only role)                      |
| `DB_PASSWORD`          | —                          | Database password                                           |
| `DB_SCHEMA`            | `public`                  | Schema to introspect and index                              |
| `DB_POOL_SIZE`         | `5`                       | SQLAlchemy connection pool size                             |
| `DB_MAX_OVERFLOW`      | `10`                      | Max extra connections above pool size                       |
| `DB_POOL_TIMEOUT`      | `30`                      | Seconds to wait for a connection                            |
| `MAX_ROWS`             | `1000`                    | Hard row cap injected into every query                      |
| `MAX_RETRIES`          | `3`                       | Self-correction loop maximum attempts                       |
| `GROQ_RETRY_DELAY`     | `1.0`                     | Seconds to wait between Groq retry calls                    |
| `ENABLE_PII_MASKING`   | `false`                   | Run Presidio PII masking on results                         |
| `CHROMA_PERSIST_DIR`   | `./chroma_db`             | ChromaDB storage directory                                  |
| `CHROMA_COLLECTION`    | `schema_embeddings`       | ChromaDB collection name                                    |
| `LANGCHAIN_TRACING_V2` | `false`                   | Enable LangSmith tracing                                    |
| `LANGCHAIN_API_KEY`    | —                          | LangSmith API key                                           |
| `LANGCHAIN_PROJECT`    | `sql-agent-pro`           | LangSmith project name                                      |
| `ENV`                  | `development`             | `development` → pretty logs, `production` → JSON logs |
| `LOG_LEVEL`            | `INFO`                    | Logging level                                               |

---

## Running Tests

```bash
# Guardrail unit tests — no DB or API key needed
pytest tests/test_guardrails.py -v

# Integration tests — all external calls mocked
pytest tests/test_agent_integration.py -v

# Full suite
pytest tests/ -v
```

---

## Docker

```bash
# All-in-one: PostgreSQL + app + auto schema index
docker-compose up --build

# App only (uses existing PostgreSQL)
docker build -t sql-agent-pro .
docker run -p 8501:8501 --env-file .env sql-agent-pro
```

---

## Streamlit Notes

To suppress the `torchvision` warnings from `transformers`:

```bash
mkdir -p ~/.streamlit
cat > ~/.streamlit/config.toml << 'EOF'
[server]
fileWatcherType = "none"
EOF
```

---

## Recommended Test Datasets

| Dataset               | Tables | Size       | Best for                                 |
| --------------------- | ------ | ---------- | ---------------------------------------- |
| Pagila (DVD Rental)   | 15     | ~100K rows | Joins, window functions, revenue queries |
| Chinook (Music Store) | 11     | ~75K rows  | Many-to-many, aggregations               |
| Northwind (ERP)       | 14     | ~50K rows  | Business analytics, supplier queries     |
| NYC Taxi Trips        | 1      | 1B+ rows   | Performance testing, time-series         |
| IMDb                  | 7      | 7M+ rows   | Complex filtering, ranking               |

Load Pagila (recommended start):

```bash
git clone https://github.com/devrimgunduz/pagila.git
sudo -u postgres psql -d pagila -f pagila/pagila-schema.sql
sudo -u postgres psql -d pagila -f pagila/pagila-data.sql
```

---

## Production Checklist

- [ ] PostgreSQL read-only user with SELECT-only grants
- [ ] `GROQ_API_KEY` in secrets manager, not in git
- [ ] `.env` in `.gitignore` (it is by default)
- [ ] `ENV=production` set (enables JSON log output)
- [ ] `LANGCHAIN_TRACING_V2=true` for LangSmith observability
- [ ] `ENABLE_PII_MASKING=true` if database contains personal data
- [ ] `MAX_ROWS` and `MAX_RETRIES` reviewed for your workload
- [ ] `GROQ_RETRY_DELAY` tuned (use Groq paid tier for production)
- [ ] Schema index rebuild automated after DDL changes
- [ ] Docker health checks monitored
- [ ] `DB_POOL_SIZE` tuned for concurrent users

---

## License

MIT — see `LICENSE` for details.
