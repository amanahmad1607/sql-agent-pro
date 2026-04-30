"""tests/test_agent_integration.py — all external calls mocked."""

import pytest
from unittest.mock import MagicMock, patch


class TestGuardrailEdgeCases:
    def test_nested_select(self):
        from utils.guardrails import validate_and_sanitize
        assert validate_and_sanitize(
            "SELECT * FROM (SELECT id FROM public.orders) sub"
        ).is_safe

    def test_cte_with_window(self):
        from utils.guardrails import validate_and_sanitize
        sql = """
        WITH r AS (SELECT id, amount,
                   ROW_NUMBER() OVER (PARTITION BY cust ORDER BY amount DESC) AS rn
                   FROM public.orders)
        SELECT * FROM r WHERE rn = 1
        """
        assert validate_and_sanitize(sql).is_safe


class TestSchemaFormatting:
    def test_format_basic(self):
        from agents.tools import format_schema_context
        schemas = [{"schema": "public", "table_name": "orders",
                    "ddl": "CREATE TABLE public.orders (id UUID);", "fk_notes": []}]
        ctx = format_schema_context(schemas)
        assert "public.orders" in ctx and "CREATE TABLE" in ctx

    def test_format_with_fk(self):
        from agents.tools import format_schema_context
        schemas = [{"schema": "public", "table_name": "order_items",
                    "ddl": "CREATE TABLE public.order_items (id UUID);",
                    "fk_notes": ["order_id → public.orders.order_id"]}]
        ctx = format_schema_context(schemas)
        assert "FK" in ctx


class TestMetadataExtractor:
    def test_detect_by_name(self):
        from agents.metadata_extractor import detect_text_columns
        rows = [{"id": 1, "notes": "long free text here", "amount": 100}]
        assert "notes" in detect_text_columns(rows)

    def test_detect_by_length(self):
        from agents.metadata_extractor import detect_text_columns
        rows = [{"id": 1, "custom_field": "x" * 60}]
        assert "custom_field" in detect_text_columns(rows)

    def test_no_text_in_numeric_table(self):
        from agents.metadata_extractor import detect_text_columns
        rows = [{"order_id": "abc", "amount": 100.0, "quantity": 5}]
        assert detect_text_columns(rows) == []

    @patch("agents.metadata_extractor.extract_metadata")
    def test_enrich_adds_columns(self, mock_extract):
        from agents.metadata_extractor import enrich_results
        mock_extract.return_value = [{
            "sentiment": "positive", "topics": ["delivery"],
            "summary": "Fast delivery", "urgency": "low",
        }]
        rows = [{"id": 1, "notes": "Great service!"}]
        enriched = enrich_results(rows, ["notes"])
        assert enriched[0]["notes__sentiment"] == "positive"
        assert enriched[0]["notes__summary"] == "Fast delivery"


class TestAgentState:
    def test_state_keys(self):
        from agents.graph import AgentState
        required = {"question", "schema_context", "annotation", "generated_sql",
                    "execution_result", "retry_count", "error_history",
                    "final_answer", "messages"}
        assert required.issubset(set(AgentState.__annotations__.keys()))

    def test_increment_retry(self):
        from agents.graph import increment_retry
        state = {
            "retry_count": 1,
            "error_history": ["first error"],
            "execution_result": {"error": "column not found"},
        }
        out = increment_retry(state)
        assert out["retry_count"] == 2
        assert "column not found" in out["error_history"]


class TestLLMFactory:
    def test_provider_info_returns_dict(self):
        from agents.llm import get_provider_info
        info = get_provider_info()
        assert "provider" in info and "model" in info

    def test_unknown_provider_raises(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {"LLM_PROVIDER": "unknown_xyz"}):
            from agents.llm import get_llm
            get_llm.cache_clear()
            with pytest.raises((ValueError, EnvironmentError)):
                get_llm()
            get_llm.cache_clear()


class TestPrompts:
    def test_correction_prompt_fills(self):
        from agents.prompts import CORRECTION_PROMPT
        filled = CORRECTION_PROMPT.format(
            error="column 'custmer_id' does not exist",
            failed_sql="SELECT custmer_id FROM orders",
            schema_context="CREATE TABLE orders (customer_id UUID);",
            question="List all orders",
        )
        assert "custmer_id" in filled

    def test_annotation_prompt_fills(self):
        from agents.prompts import ANNOTATION_PROMPT
        filled = ANNOTATION_PROMPT.format(
            question="Top 5 customers",
            schema_context="CREATE TABLE customers (id UUID, name TEXT);",
        )
        assert "tables_needed" in filled
