"""
agents/llm.py
Centralized LLM factory. Groq is the default provider.
Switch via LLM_PROVIDER env var — the rest of the codebase is unaffected.

Supported providers:
  groq      → langchain-groq  (default, fastest)
  openai    → langchain-openai
  anthropic → langchain-anthropic

Groq model recommendations for SQL generation:
  llama-3.3-70b-versatile  — best quality  (default)
  llama3-70b-8192          — great quality, higher context
  mixtral-8x7b-32768       — fast, good quality
  llama3-8b-8192           — blazing fast, lighter tasks
"""

from __future__ import annotations

import os
import structlog
from functools import lru_cache

log = structlog.get_logger(__name__)

# Groq-specific safe defaults
_GROQ_DEFAULTS = {
    "temperature": 0,
    "max_tokens": 4096,
}

_GROQ_MODELS = {
    "llama-3.3-70b-versatile",
    "llama3-70b-8192",
    "llama3-8b-8192",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
}


@lru_cache(maxsize=1)
def get_llm():
    """
    Singleton LLM instance. Cached so the same object is reused
    across all LangGraph nodes without reconnecting.
    """
    provider = os.getenv("LLM_PROVIDER", "groq").lower()
    model = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

    log.info("llm.initializing", provider=provider, model=model)

    if provider == "groq":
        _assert_key("GROQ_API_KEY", "https://console.groq.com")
        from langchain_groq import ChatGroq
        llm = ChatGroq(
            model=model,
            temperature=_GROQ_DEFAULTS["temperature"],
            max_tokens=_GROQ_DEFAULTS["max_tokens"],
            groq_api_key=os.environ["GROQ_API_KEY"],
        )

    elif provider == "openai":
        _assert_key("OPENAI_API_KEY", "https://platform.openai.com")
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(model=model, temperature=0)

    elif provider == "anthropic":
        _assert_key("ANTHROPIC_API_KEY", "https://console.anthropic.com")
        from langchain_anthropic import ChatAnthropic
        llm = ChatAnthropic(model=model, temperature=0)

    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER='{provider}'. "
            "Valid options: groq, openai, anthropic"
        )

    log.info("llm.ready", provider=provider, model=model)
    return llm


def _assert_key(env_var: str, signup_url: str) -> None:
    if not os.getenv(env_var):
        raise EnvironmentError(
            f"{env_var} is not set.\n"
            f"Get your API key at: {signup_url}\n"
            f"Then add it to your .env file."
        )


def get_provider_info() -> dict:
    """Return current LLM config — useful for the UI sidebar."""
    return {
        "provider": os.getenv("LLM_PROVIDER", "groq"),
        "model": os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
    }
