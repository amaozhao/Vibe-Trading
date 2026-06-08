"""Tests for startup preflight checks."""

from __future__ import annotations

import sys
from types import SimpleNamespace

from src import preflight


def test_akshare_check_uses_spec_without_import(monkeypatch) -> None:
    """AKShare's package import is heavy; preflight should only check discovery."""
    monkeypatch.delitem(sys.modules, "akshare", raising=False)
    monkeypatch.setattr(preflight, "find_spec", lambda name: object() if name == "akshare" else None)

    result = preflight._check_akshare()

    assert result.status == "ready"
    assert result.message == "installed"
    assert "akshare" not in sys.modules


def test_akshare_check_skips_when_missing(monkeypatch) -> None:
    monkeypatch.setattr(preflight, "find_spec", lambda name: None)

    result = preflight._check_akshare()

    assert result.status == "skipped"
    assert result.message == "package not installed"


def test_minimax_token_plan_preflight_uses_token_plan_base_url(monkeypatch) -> None:
    """Token Plan is not OpenAI-compatible; preflight must not require
    OPENAI_BASE_URL after provider env sync clears it."""
    monkeypatch.setenv("LANGCHAIN_PROVIDER", "minimax-token-plan")
    monkeypatch.setenv("LANGCHAIN_MODEL_NAME", "MiniMax-M3")
    monkeypatch.setenv("MINIMAX_TOKEN_PLAN_BASE_URL", "https://api.minimaxi.com/anthropic")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_BASE", raising=False)

    def fake_get(url: str, timeout: int) -> SimpleNamespace:
        return SimpleNamespace(url=url, timeout=timeout)

    monkeypatch.setattr("requests.get", fake_get)

    result = preflight._check_llm_provider()

    assert result.status == "ready"
    assert "MiniMax-M3 via https://api.minimaxi.com/anthropic" == result.message
