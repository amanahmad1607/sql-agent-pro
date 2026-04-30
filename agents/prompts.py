"""
agents/prompts.py
All LLM prompt templates for the SQL agent.
Tuned for Llama-3.3-70b on Groq — concise instructions work better
than verbose ones at this model size.
"""

SYSTEM_PROMPT = """You are an expert PostgreSQL analyst.
Translate natural language questions into correct, efficient SQL SELECT queries.

Rules:
1. ONLY write SELECT statements. Never write INSERT, UPDATE, DELETE, DROP, CREATE, or ALTER.
2. Always use fully-qualified table names: schema.table_name.
3. Use CTEs (WITH clauses) for multi-step logic.
4. Use window functions (ROW_NUMBER, RANK, LAG, LEAD) instead of correlated subqueries.
5. Always GROUP BY every non-aggregated SELECT column.
6. Handle NULLs with COALESCE or IS NULL where relevant.
7. Do NOT add a LIMIT clause — the system enforces its own.
8. Return ONLY the raw SQL. No markdown, no explanation, no code fences.
"""

CORRECTION_PROMPT = """The SQL query you wrote caused this error:

ERROR:
{error}

ORIGINAL QUERY:
{failed_sql}

SCHEMA:
{schema_context}

QUESTION:
{question}

Diagnose the root cause and rewrite the query to fix it.
Common causes: wrong column name, missing JOIN, ambiguous column, bad aggregation, type mismatch.
Return ONLY the corrected SQL. No explanation.
"""

ANNOTATION_PROMPT = """Analyze this question against the schema and return a JSON object.

QUESTION: {question}

SCHEMA:
{schema_context}

Return ONLY this JSON (no markdown, no preamble):
{{
  "tables_needed": ["table1", "table2"],
  "key_columns": ["col1", "col2"],
  "join_conditions": ["t1.id = t2.fk_id"],
  "filters": ["status = 'active'"],
  "aggregations": ["COUNT(*)", "SUM(amount)"],
  "order_by": ["created_at DESC"],
  "enriched_question": "Precise restatement with actual column/table names"
}}
"""

SUMMARISATION_PROMPT = """Write a 2–3 sentence business insight from this query result.
Use specific numbers. Be concise.

QUESTION: {question}
SQL: {sql}
ROW COUNT: {row_count}
SAMPLE (first 5 rows):
{sample_data}
"""

FEW_SHOT_EXAMPLES = [
    {
        "question": "Top 5 customers by total revenue this year",
        "sql": (
            "WITH rev AS (\n"
            "    SELECT c.customer_id, c.name,\n"
            "           SUM(o.amount) AS total_revenue,\n"
            "           COUNT(o.order_id) AS order_count\n"
            "    FROM public.customers c\n"
            "    JOIN public.orders o ON c.customer_id = o.customer_id\n"
            "    WHERE o.created_at >= DATE_TRUNC('year', NOW())\n"
            "      AND o.status = 'completed'\n"
            "    GROUP BY c.customer_id, c.name\n"
            ")\n"
            "SELECT name, total_revenue, order_count,\n"
            "       RANK() OVER (ORDER BY total_revenue DESC) AS rank\n"
            "FROM rev\n"
            "ORDER BY total_revenue DESC;"
        ),
    },
    {
        "question": "Month-over-month revenue growth this year",
        "sql": (
            "WITH monthly AS (\n"
            "    SELECT DATE_TRUNC('month', created_at) AS month,\n"
            "           SUM(amount) AS revenue\n"
            "    FROM public.orders\n"
            "    WHERE EXTRACT(YEAR FROM created_at) = EXTRACT(YEAR FROM NOW())\n"
            "      AND status = 'completed'\n"
            "    GROUP BY 1\n"
            ")\n"
            "SELECT TO_CHAR(month, 'YYYY-MM') AS month, revenue,\n"
            "       LAG(revenue) OVER (ORDER BY month) AS prev_revenue,\n"
            "       ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY month))\n"
            "             / NULLIF(LAG(revenue) OVER (ORDER BY month), 0), 2) AS growth_pct\n"
            "FROM monthly\n"
            "ORDER BY month;"
        ),
    },
]
