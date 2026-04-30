"""tests/test_guardrails.py — runs with no DB or API key."""

import pytest
from utils.guardrails import validate_and_sanitize, GuardrailResult


class TestGuardrails:
    def test_valid_select(self):
        r = validate_and_sanitize("SELECT id, name FROM public.users WHERE active = true")
        assert r.is_safe and "LIMIT" in r.safe_sql

    def test_drop_blocked(self):
        assert not validate_and_sanitize("DROP TABLE public.users").is_safe

    def test_delete_blocked(self):
        assert not validate_and_sanitize("DELETE FROM public.orders WHERE id = 1").is_safe

    def test_update_blocked(self):
        assert not validate_and_sanitize("UPDATE public.users SET active = false").is_safe

    def test_insert_blocked(self):
        assert not validate_and_sanitize("INSERT INTO public.users (name) VALUES ('x')").is_safe

    def test_multiple_statements_blocked(self):
        assert not validate_and_sanitize("SELECT 1; DROP TABLE users;").is_safe

    def test_limit_injected(self):
        r = validate_and_sanitize("SELECT * FROM public.products")
        assert r.is_safe and "__limited__" in r.safe_sql

    def test_cte_allowed(self):
        sql = """
        WITH s AS (SELECT customer_id, SUM(amount) AS total
                   FROM public.orders GROUP BY customer_id)
        SELECT * FROM s ORDER BY total DESC
        """
        assert validate_and_sanitize(sql).is_safe

    def test_window_function_allowed(self):
        sql = """
        SELECT id, name,
               ROW_NUMBER() OVER (PARTITION BY dept ORDER BY salary DESC) AS rn
        FROM public.employees
        """
        assert validate_and_sanitize(sql).is_safe

    def test_union_allowed(self):
        assert validate_and_sanitize("SELECT 'a' AS x UNION ALL SELECT 'b' AS x").is_safe

    def test_semicolon_stripped(self):
        assert validate_and_sanitize("SELECT 1;").is_safe
