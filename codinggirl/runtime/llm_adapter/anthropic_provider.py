"""
Anthropic Claude API Provider

支持 Claude 的 tool_use 消息格式
"""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass

from codinggirl.runtime.llm_adapter.models import ChatMessage, LLMConfig, LLMResponse, ToolCall, ToolSchema


def _messages_to_anthropic_payload(messages: list[ChatMessage]) -> tuple[str | None, list[dict[str, object]]]:
    """
    转换消息为 Anthropic 格式

    Returns:
        (system_prompt, messages_payload)
    """
    system_prompt: str | None = None
    out: list[dict[str, object]] = []

    for m in messages:
        if m.role == "system":
            # Anthropic 的 system 是单独参数
            system_prompt = m.content
            continue

        if m.role == "tool":
            # tool result 格式
            out.append({
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": m.tool_call_id,
                        "content": m.content,
                    }
                ],
            })
        else:
            # user/assistant
            out.append({
                "role": m.role,
                "content": m.content,
            })

    return system_prompt, out


def _tools_to_anthropic_payload(tools: list[ToolSchema]) -> list[dict[str, object]]:
    """转换工具 schema 为 Anthropic 格式"""
    return [
        {
            "name": t.name,
            "description": t.description,
            "input_schema": t.input_schema,
        }
        for t in tools
    ]


def _parse_anthropic_response(resp: dict[str, object]) -> LLMResponse:
    """解析 Anthropic API 响应"""
    content_blocks = resp.get("content")
    if not isinstance(content_blocks, list):
        raise ValueError("invalid anthropic response: missing content")

    # 提取文本和 tool_use blocks
    text_parts: list[str] = []
    tool_calls: list[ToolCall] = []

    for block in content_blocks:
        if not isinstance(block, dict):
            continue

        block_type = block.get("type")

        if block_type == "text":
            text = block.get("text")
            if isinstance(text, str):
                text_parts.append(text)

        elif block_type == "tool_use":
            tool_id = block.get("id")
            tool_name = block.get("name")
            tool_input = block.get("input")

            if isinstance(tool_id, str) and isinstance(tool_name, str) and isinstance(tool_input, dict):
                tool_calls.append(
                    ToolCall(
                        id=tool_id,
                        name=tool_name,
                        arguments_json=json.dumps(tool_input, ensure_ascii=False),
                    )
                )

    content_text = "\n".join(text_parts)

    stop_reason = resp.get("stop_reason")
    model = resp.get("model")

    return LLMResponse(
        model=model if isinstance(model, str) else "unknown",
        content=content_text,
        finish_reason=stop_reason if isinstance(stop_reason, str) else None,
        tool_calls=tool_calls,
        raw=resp,
    )


@dataclass(frozen=True, slots=True)
class AnthropicProvider:
    """Anthropic Claude API Provider"""

    config: LLMConfig

    def chat(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[ToolSchema] | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        base_url = self.config.base_url or "https://api.anthropic.com"
        endpoint = base_url.rstrip("/") + "/v1/messages"
        api_key = self.config.api_key or os.environ.get("ANTHROPIC_API_KEY")

        if not api_key:
            raise ValueError("missing api key (config.api_key or ANTHROPIC_API_KEY)")

        # 转换消息格式
        system_prompt, messages_payload = _messages_to_anthropic_payload(messages)

        payload: dict[str, object] = {
            "model": self.config.model,
            "messages": messages_payload,
            "max_tokens": 4096,
            "temperature": temperature,
        }

        if system_prompt:
            payload["system"] = system_prompt

        if tools:
            payload["tools"] = _tools_to_anthropic_payload(tools)

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
        )

        with urllib.request.urlopen(req, timeout=self.config.timeout_sec) as resp:
            raw = resp.read().decode("utf-8", errors="replace")

        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("invalid response: root is not object")

        return _parse_anthropic_response(parsed)
