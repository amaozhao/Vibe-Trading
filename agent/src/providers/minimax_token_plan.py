"""MiniMax Token Plan Anthropic-compatible provider.

MiniMax Token Plan keys are separate from MiniMax pay-as-you-go API keys. This
adapter follows MiniMax's Anthropic-compatible endpoint instead of routing those
keys through the existing OpenAI-compatible MiniMax provider.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional
from urllib.parse import urlparse

from src.config.accessor import get_env_config

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore


DEFAULT_MINIMAX_TOKEN_PLAN_URL = "https://api.minimaxi.com/anthropic"
DEFAULT_MINIMAX_TOKEN_PLAN_MAX_TOKENS = 16_000


@dataclass
class MiniMaxTokenPlanMessage:
    """Small LangChain-like message object used by ChatLLM."""

    content: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    additional_kwargs: dict[str, Any] = field(default_factory=dict)
    response_metadata: dict[str, Any] = field(default_factory=lambda: {"finish_reason": "stop"})
    usage_metadata: dict[str, int] | None = None

    def __add__(self, other: "MiniMaxTokenPlanMessage") -> "MiniMaxTokenPlanMessage":
        reasoning = (
            self.additional_kwargs.get("reasoning_content", "")
            + other.additional_kwargs.get("reasoning_content", "")
        )
        usage = _merge_usage(self.usage_metadata, other.usage_metadata)
        return MiniMaxTokenPlanMessage(
            content=(self.content or "") + (other.content or ""),
            tool_calls=[*self.tool_calls, *other.tool_calls],
            additional_kwargs={"reasoning_content": reasoning} if reasoning else {},
            response_metadata={
                "finish_reason": other.response_metadata.get(
                    "finish_reason",
                    self.response_metadata.get("finish_reason", "stop"),
                )
            },
            usage_metadata=usage,
        )


def validate_minimax_token_plan_base_url(url: str) -> str:
    """Validate MiniMax's Anthropic-compatible Token Plan base URL."""
    value = (url or DEFAULT_MINIMAX_TOKEN_PLAN_URL).strip().rstrip("/")
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or parsed.netloc not in {"api.minimaxi.com", "api.minimax.io"}
        or parsed.path != "/anthropic"
    ):
        raise ValueError(
            "MiniMax Token Plan requires an Anthropic-compatible base URL such as "
            "https://api.minimaxi.com/anthropic"
        )
    return value


def _endpoint(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/v1/messages"


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
        "User-Agent": "vibe-trading (python)",
    }


def _decode_tool_args(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}
    return parsed if isinstance(parsed, dict) else {"raw": raw}


def _convert_user_content(content: Any) -> Any:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    converted: list[dict[str, Any]] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "text":
            converted.append({"type": "text", "text": item.get("text", "")})
        elif item.get("type") == "image_url":
            image_url = item.get("image_url") or {}
            url = image_url.get("url")
            if url:
                converted.append({"type": "image", "source": {"type": "url", "url": url}})
    return converted or ""


def _convert_assistant_message(msg: dict[str, Any]) -> dict[str, Any] | None:
    content_blocks: list[dict[str, Any]] = []
    content = msg.get("content")
    if isinstance(content, str) and content:
        content_blocks.append({"type": "text", "text": content})

    for tool_call in msg.get("tool_calls", []) or []:
        if not isinstance(tool_call, dict):
            continue
        fn = tool_call.get("function") or {}
        name = fn.get("name")
        if not name:
            continue
        content_blocks.append({
            "type": "tool_use",
            "id": tool_call.get("id") or f"toolu_{len(content_blocks)}",
            "name": name,
            "input": _decode_tool_args(fn.get("arguments")),
        })

    if not content_blocks:
        return None
    return {"role": "assistant", "content": content_blocks}


def _convert_tool_result(msg: dict[str, Any]) -> dict[str, Any]:
    content = msg.get("content")
    if not isinstance(content, str):
        content = json.dumps(content, ensure_ascii=False)
    return {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": msg.get("tool_call_id") or "toolu_0",
                "content": content,
            }
        ],
    }


def _convert_messages(messages: list[dict[str, Any]]) -> tuple[str | None, list[dict[str, Any]]]:
    system_parts: list[str] = []
    converted: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")
        if role == "system":
            if isinstance(content, str) and content:
                system_parts.append(content)
        elif role == "user":
            converted.append({"role": "user", "content": _convert_user_content(content)})
        elif role == "assistant":
            assistant_msg = _convert_assistant_message(msg)
            if assistant_msg is not None:
                converted.append(assistant_msg)
        elif role == "tool":
            converted.append(_convert_tool_result(msg))
    return ("\n\n".join(system_parts) if system_parts else None), converted


def _convert_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for tool in tools or []:
        fn = (tool.get("function") or {}) if tool.get("type") == "function" else tool
        name = fn.get("name")
        if not name:
            continue
        schema = fn.get("parameters") or {}
        converted.append({
            "name": name,
            "description": fn.get("description") or "",
            "input_schema": schema if isinstance(schema, dict) else {},
        })
    return converted


def _finish_reason(stop_reason: str | None) -> str:
    return {
        "tool_use": "tool_calls",
        "end_turn": "stop",
        "stop_sequence": "stop",
        "max_tokens": "length",
    }.get(stop_reason or "end_turn", "stop")


def _usage(raw: dict[str, Any] | None) -> dict[str, int] | None:
    if not isinstance(raw, dict):
        return None
    input_tokens = int(raw.get("input_tokens") or 0)
    output_tokens = int(raw.get("output_tokens") or 0)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": int(raw.get("total_tokens") or input_tokens + output_tokens),
    }


def _merge_usage(
    left: dict[str, int] | None,
    right: dict[str, int] | None,
) -> dict[str, int] | None:
    if left is None:
        return right
    if right is None:
        return left
    return {
        "input_tokens": left.get("input_tokens", 0) + right.get("input_tokens", 0),
        "output_tokens": left.get("output_tokens", 0) + right.get("output_tokens", 0),
        "total_tokens": left.get("total_tokens", 0) + right.get("total_tokens", 0),
    }


class MiniMaxTokenPlanLLM:
    """Minimal LangChain-compatible adapter for MiniMax Token Plan."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        temperature: float = 1.0,
        timeout: int = 120,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> None:
        if httpx is None:
            raise RuntimeError("MiniMax Token Plan requires httpx. Install dependencies first.")
        config = get_env_config().llm
        self.model = model
        self.api_key = api_key or config.minimax_token_plan_api_key
        if not self.api_key:
            raise RuntimeError("MINIMAX_TOKEN_PLAN_API_KEY is not set")
        self.base_url = validate_minimax_token_plan_base_url(
            base_url or config.minimax_token_plan_base_url
        )
        self.temperature = temperature
        self.timeout = timeout
        self.max_tokens = max_tokens or config.minimax_token_plan_max_tokens
        self.tools = tools or []

    def bind_tools(self, tools: list[dict[str, Any]]) -> "MiniMaxTokenPlanLLM":
        return MiniMaxTokenPlanLLM(
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=self.temperature,
            timeout=self.timeout,
            max_tokens=self.max_tokens,
            tools=tools,
        )

    def _body(self, messages: list[dict[str, Any]], *, stream: bool) -> dict[str, Any]:
        system, anthropic_messages = _convert_messages(messages)
        body: dict[str, Any] = {
            "model": self.model,
            "messages": anthropic_messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": stream,
        }
        if system:
            body["system"] = system
        tools = _convert_tools(self.tools)
        if tools:
            body["tools"] = tools
        return body

    @staticmethod
    def _message_from_response(payload: dict[str, Any]) -> MiniMaxTokenPlanMessage:
        text_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        for block in payload.get("content") or []:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text" and block.get("text"):
                text_parts.append(str(block["text"]))
            elif block_type in {"thinking", "reasoning"}:
                value = block.get("thinking") or block.get("text")
                if value:
                    reasoning_parts.append(str(value))
            elif block_type == "tool_use":
                tool_calls.append({
                    "id": block.get("id") or f"toolu_{len(tool_calls)}",
                    "name": block.get("name") or "",
                    "args": block.get("input") if isinstance(block.get("input"), dict) else {},
                })
        reasoning = "".join(reasoning_parts)
        return MiniMaxTokenPlanMessage(
            content="".join(text_parts),
            tool_calls=tool_calls,
            additional_kwargs={"reasoning_content": reasoning} if reasoning else {},
            response_metadata={"finish_reason": _finish_reason(payload.get("stop_reason"))},
            usage_metadata=_usage(payload.get("usage")),
        )

    def invoke(
        self,
        messages: list[dict[str, Any]],
        config: Optional[dict[str, Any]] = None,
    ) -> MiniMaxTokenPlanMessage:
        timeout = (config or {}).get("timeout") or self.timeout
        if httpx is None:
            raise RuntimeError("MiniMax Token Plan requires httpx. Install backend dependencies first.")
        with httpx.Client(timeout=timeout, follow_redirects=True, trust_env=True) as client:
            response = client.post(
                _endpoint(self.base_url),
                headers=_headers(self.api_key),
                json=self._body(messages, stream=False),
            )
        if response.status_code >= 400:
            raise RuntimeError(f"MiniMax Token Plan HTTP {response.status_code}: {response.text[:500]}")
        return self._message_from_response(response.json())

    def stream(
        self,
        messages: list[dict[str, Any]],
        config: Optional[dict[str, Any]] = None,
    ) -> Iterable[MiniMaxTokenPlanMessage]:
        # The project only needs a LangChain-compatible iterable here. Use the
        # non-streaming endpoint so Anthropic-compatible Token Plan works without
        # adding a second SSE parser surface.
        yield self.invoke(messages, config=config)

    async def ainvoke(
        self,
        messages: list[dict[str, Any]],
        config: Optional[dict[str, Any]] = None,
    ) -> MiniMaxTokenPlanMessage:
        return await asyncio.to_thread(self.invoke, messages, config)
