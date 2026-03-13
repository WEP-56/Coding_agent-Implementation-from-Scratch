from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass

from codinggirl.runtime.llm_adapter.models import ChatMessage, LLMConfig, LLMResponse, ToolCall, ToolSchema


def _messages_to_payload(messages: list[ChatMessage]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for m in messages:
        item: dict[str, object] = {"role": m.role, "content": m.content}

        # tool 消息需要 tool_call_id，不需要 name
        if m.role == "tool":
            if m.tool_call_id:
                item["tool_call_id"] = m.tool_call_id
        elif m.role == "assistant":
            # assistant 消息可能包含 tool_calls
            if m.tool_calls:
                item["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": tc.arguments_json,
                        },
                    }
                    for tc in m.tool_calls
                ]
        else:
            # 其他消息可以有 name
            if m.name:
                item["name"] = m.name

        out.append(item)
    return out


def _tools_to_payload(tools: list[ToolSchema]) -> list[dict[str, object]]:
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.input_schema,
            },
        }
        for t in tools
    ]


def _parse_openai_response(resp: dict[str, object]) -> LLMResponse:
    choices = resp.get("choices")
    if not isinstance(choices, list) or len(choices) == 0:
        raise ValueError("invalid openai response: missing choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise ValueError("invalid openai response: malformed choice")

    finish_reason = first.get("finish_reason")
    message = first.get("message")
    if not isinstance(message, dict):
        raise ValueError("invalid openai response: missing message")

    content = message.get("content")
    if content is None:
        content_text = ""
    elif isinstance(content, str):
        content_text = content
    else:
        content_text = json.dumps(content, ensure_ascii=False)

    tool_calls_raw = message.get("tool_calls")
    tool_calls: list[ToolCall] = []
    if isinstance(tool_calls_raw, list):
        for tc in tool_calls_raw:
            if not isinstance(tc, dict):
                continue
            fn = tc.get("function")
            if not isinstance(fn, dict):
                continue
            name = fn.get("name")
            args = fn.get("arguments")
            tc_id = tc.get("id")
            if isinstance(name, str) and isinstance(args, str) and isinstance(tc_id, str):
                tool_calls.append(ToolCall(id=tc_id, name=name, arguments_json=args))

    model = resp.get("model")
    model_name = model if isinstance(model, str) else "unknown"
    return LLMResponse(
        model=model_name,
        content=content_text,
        finish_reason=finish_reason if isinstance(finish_reason, str) else None,
        tool_calls=tool_calls,
        raw=resp,
    )


@dataclass(frozen=True, slots=True)
class OpenAICompatibleProvider:
    config: LLMConfig

    def chat(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[ToolSchema] | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        base_url = self.config.base_url or "https://api.openai.com"
        base_url = base_url.rstrip("/")

        # 智能构建 endpoint：如果 base_url 已经包含完整路径，直接使用
        if base_url.endswith("/chat/completions"):
            endpoint = base_url
        elif base_url.endswith("/v1"):
            endpoint = base_url + "/chat/completions"
        else:
            endpoint = base_url + "/v1/chat/completions"

        api_key = self.config.api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("missing api key (config.api_key or OPENAI_API_KEY)")

        payload: dict[str, object] = {
            "model": self.config.model,
            "messages": _messages_to_payload(messages),
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = _tools_to_payload(tools)
            payload["tool_choice"] = "auto"

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )

        with urllib.request.urlopen(req, timeout=self.config.timeout_sec) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("invalid response: root is not object")
        return _parse_openai_response(parsed)
