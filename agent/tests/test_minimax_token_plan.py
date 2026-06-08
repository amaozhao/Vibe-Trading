"""Tests for MiniMax Token Plan Anthropic-compatible provider."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.providers import llm as llm_mod
from src.providers.minimax_token_plan import (
    DEFAULT_MINIMAX_TOKEN_PLAN_URL,
    MiniMaxTokenPlanLLM,
    validate_minimax_token_plan_base_url,
)


def test_provider_metadata_exposes_token_plan_anthropic_endpoint() -> None:
    providers_path = Path(__file__).resolve().parents[1] / "src" / "providers" / "llm_providers.json"
    providers = json.loads(providers_path.read_text(encoding="utf-8"))
    provider = next(item for item in providers if item["name"] == "minimax-token-plan")

    assert provider["label"] == "MiniMax Token Plan"
    assert provider["api_key_env"] == "MINIMAX_TOKEN_PLAN_API_KEY"
    assert provider["base_url_env"] == "MINIMAX_TOKEN_PLAN_BASE_URL"
    assert provider["default_base_url"] == DEFAULT_MINIMAX_TOKEN_PLAN_URL
    assert provider["default_model"] == "MiniMax-M3"


def test_build_llm_returns_minimax_token_plan_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_mod, "_dotenv_loaded", True)
    monkeypatch.setenv("LANGCHAIN_PROVIDER", "minimax-token-plan")
    monkeypatch.setenv("LANGCHAIN_MODEL_NAME", "MiniMax-M3")
    monkeypatch.setenv("MINIMAX_TOKEN_PLAN_API_KEY", "token-plan-key")
    monkeypatch.setenv("MINIMAX_TOKEN_PLAN_BASE_URL", DEFAULT_MINIMAX_TOKEN_PLAN_URL)

    adapter = llm_mod.build_llm()

    assert isinstance(adapter, MiniMaxTokenPlanLLM)
    assert adapter.model == "MiniMax-M3"
    assert adapter.base_url == DEFAULT_MINIMAX_TOKEN_PLAN_URL


def test_minimax_token_plan_body_uses_anthropic_messages_format() -> None:
    adapter = MiniMaxTokenPlanLLM(model="MiniMax-M3", api_key="token-plan-key")
    body = adapter.bind_tools([
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a file",
                "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
            },
        }
    ])._body(
        [
            {"role": "system", "content": "You are careful."},
            {"role": "user", "content": "Open README."},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "toolu_1",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": "{\"path\":\"README.md\"}"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "toolu_1", "content": "README contents"},
        ],
        stream=False,
    )

    assert body["model"] == "MiniMax-M3"
    assert body["system"] == "You are careful."
    assert body["messages"][0] == {"role": "user", "content": "Open README."}
    assert body["messages"][1]["role"] == "assistant"
    assert body["messages"][1]["content"][0]["type"] == "tool_use"
    assert body["messages"][1]["content"][0]["name"] == "read_file"
    assert body["messages"][2]["role"] == "user"
    assert body["messages"][2]["content"][0]["type"] == "tool_result"
    assert body["tools"][0]["input_schema"]["properties"]["path"]["type"] == "string"


def test_minimax_token_plan_max_tokens_is_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINIMAX_TOKEN_PLAN_MAX_TOKENS", "16000")
    adapter = MiniMaxTokenPlanLLM(model="MiniMax-M3", api_key="token-plan-key")

    body = adapter._body([{"role": "user", "content": "Write a long report."}], stream=False)

    assert body["max_tokens"] == 16000


def test_minimax_token_plan_parses_text_and_tool_use_response() -> None:
    message = MiniMaxTokenPlanLLM._message_from_response({
        "content": [
            {"type": "thinking", "thinking": "Need a file."},
            {"type": "text", "text": "I will read it."},
            {"type": "tool_use", "id": "toolu_1", "name": "read_file", "input": {"path": "README.md"}},
        ],
        "stop_reason": "tool_use",
        "usage": {"input_tokens": 10, "output_tokens": 5},
    })

    assert message.content == "I will read it."
    assert message.additional_kwargs["reasoning_content"] == "Need a file."
    assert message.tool_calls == [{"id": "toolu_1", "name": "read_file", "args": {"path": "README.md"}}]
    assert message.response_metadata["finish_reason"] == "tool_calls"
    assert message.usage_metadata == {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}


def test_minimax_token_plan_base_url_is_anthropic_endpoint() -> None:
    assert validate_minimax_token_plan_base_url("https://api.minimaxi.com/anthropic/") == DEFAULT_MINIMAX_TOKEN_PLAN_URL

    with pytest.raises(ValueError, match="Anthropic-compatible"):
        validate_minimax_token_plan_base_url("https://api.minimaxi.com/v1")
