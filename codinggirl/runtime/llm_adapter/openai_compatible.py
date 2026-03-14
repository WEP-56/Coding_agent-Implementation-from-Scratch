from __future__ import annotations

import json
import os
import random
import time
import urllib.request
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlparse, urlunparse

from codinggirl.runtime.llm_adapter.models import (
    ChatMessage,
    LLMConfig,
    LLMResponse,
    ToolCall,
    ToolSchema,
)


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def _messages_to_payload_tools(messages: list[ChatMessage]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for m in messages:
        item: dict[str, object] = {"role": m.role, "content": m.content}

        if m.role == "tool":
            if m.tool_call_id:
                item["tool_call_id"] = m.tool_call_id
        elif m.role == "assistant":
            if m.tool_calls:
                item["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": tc.arguments_json},
                    }
                    for tc in m.tool_calls
                ]
        else:
            if m.name:
                item["name"] = m.name

        out.append(item)
    return out


def _messages_to_payload_legacy(messages: list[ChatMessage]) -> list[dict[str, object]]:
    """
    Compatibility mode for servers that support legacy function calling but not `tools`.

    - Converts `tool` role messages into legacy `function` role messages when possible.
    - Serializes assistant tool calls via `function_call` (single call).
    """
    out: list[dict[str, object]] = []
    for m in messages:
        role = m.role
        if role == "tool" and m.name:
            role = "function"

        item: dict[str, object] = {"role": role, "content": m.content}
        if role == "function" and m.name:
            item["name"] = m.name
        elif m.name and role in {"system", "user"}:
            item["name"] = m.name

        if role == "assistant" and m.tool_calls:
            first = m.tool_calls[0]
            item["function_call"] = {"name": first.name, "arguments": first.arguments_json}

        out.append(item)
    return out


def _tools_to_payload_tools(tools: list[ToolSchema]) -> list[dict[str, object]]:
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


def _tools_to_payload_legacy(tools: list[ToolSchema]) -> list[dict[str, object]]:
    return [
        {
            "name": t.name,
            "description": t.description,
            "parameters": t.input_schema,
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

    tool_calls: list[ToolCall] = []
    tool_calls_raw = message.get("tool_calls")
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

    function_call_raw = message.get("function_call")
    if isinstance(function_call_raw, dict):
        name = function_call_raw.get("name")
        args = function_call_raw.get("arguments")
        if isinstance(name, str):
            if isinstance(args, str):
                arguments_json = args
            elif args is None:
                arguments_json = "{}"
            else:
                arguments_json = json.dumps(args, ensure_ascii=False)
            tool_calls.append(ToolCall(id="function_call", name=name, arguments_json=arguments_json))

    model = resp.get("model")
    model_name = model if isinstance(model, str) else "unknown"
    return LLMResponse(
        model=model_name,
        content=content_text,
        finish_reason=finish_reason if isinstance(finish_reason, str) else None,
        tool_calls=tool_calls,
        raw=resp,
    )


def _build_chat_completions_endpoint(base_url: str) -> str:
    base_url = base_url.rstrip("/")
    if base_url.endswith("/chat/completions"):
        return base_url

    parsed = urlparse(base_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))

    if parsed.path.rstrip("/").endswith("/v1"):
        path = parsed.path.rstrip("/") + "/chat/completions"
    else:
        path = parsed.path.rstrip("/") + "/v1/chat/completions"

    rebuilt = parsed._replace(path=path, query="")
    url = urlunparse(rebuilt)
    if query:
        url = url + "?" + "&".join([f"{k}={v}" for k, v in query.items()])
    return url


def _extract_error_message(err_body: str) -> str:
    try:
        parsed = json.loads(err_body)
    except Exception:
        return err_body.strip()

    if isinstance(parsed, dict):
        maybe_error = parsed.get("error")
        if isinstance(maybe_error, dict):
            msg = maybe_error.get("message")
            if isinstance(msg, str) and msg.strip():
                return msg.strip()
        msg2 = parsed.get("message")
        if isinstance(msg2, str) and msg2.strip():
            return msg2.strip()
    return err_body.strip()


def _looks_like_tools_unsupported(message: str) -> bool:
    lower = message.lower()
    return any(
        needle in lower
        for needle in [
            "unknown field 'tools'",
            "unknown field \"tools\"",
            "unknown field 'tool_choice'",
            "unknown field \"tool_choice\"",
            "unexpected field: tools",
            "unexpected field: tool_choice",
            "tool_choice is not supported",
            "tools is not supported",
            "tool calling is not supported",
        ]
    )


def _backoff_sleep(attempt: int, *, base: float = 0.5, cap: float = 8.0) -> None:
    delay = min(cap, base * (2 ** max(0, attempt - 1)))
    delay = delay * (0.7 + random.random() * 0.6)
    time.sleep(delay)


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
        endpoint = _build_chat_completions_endpoint(base_url)

        api_key = self.config.api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("missing api key (config.api_key or OPENAI_API_KEY)")

        max_attempts = int(os.environ.get("CODINGGIRL_LLM_MAX_ATTEMPTS", "3") or "3")
        use_legacy = False

        for attempt in range(1, max_attempts + 1):
            if use_legacy:
                payload: dict[str, object] = {
                    "model": self.config.model,
                    "messages": _messages_to_payload_legacy(messages),
                    "temperature": temperature,
                }
                if tools:
                    payload["functions"] = _tools_to_payload_legacy(tools)
                    payload["function_call"] = "auto"
            else:
                payload = {
                    "model": self.config.model,
                    "messages": _messages_to_payload_tools(messages),
                    "temperature": temperature,
                }
                if tools:
                    payload["tools"] = _tools_to_payload_tools(tools)
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

            try:
                with urllib.request.urlopen(req, timeout=self.config.timeout_sec) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
                parsed = json.loads(raw)
                if not isinstance(parsed, dict):
                    raise ValueError("invalid response: root is not object")
                return _parse_openai_response(parsed)

            except TimeoutError as e:
                if attempt < max_attempts:
                    _backoff_sleep(attempt)
                    continue
                summary = {
                    "endpoint": endpoint,
                    "reason": str(e),
                    "model": str(self.config.model),
                    "timeout_sec": int(self.config.timeout_sec),
                    "tools_mode": "legacy" if use_legacy else "tools",
                }
                raise ValueError(
                    "openai-compatible request failed: " + json.dumps(summary, ensure_ascii=False)
                ) from None

            except HTTPError as e:
                status = int(getattr(e, "code", 0) or 0)
                try:
                    err_body = e.read().decode("utf-8", errors="replace")
                except Exception:
                    err_body = ""

                err_message = _extract_error_message(err_body)

                if tools and not use_legacy and status == 400 and _looks_like_tools_unsupported(err_message):
                    use_legacy = True
                    continue

                if attempt < max_attempts and (status == 429 or 500 <= status <= 599):
                    _backoff_sleep(attempt)
                    continue

                summary = {
                    "endpoint": endpoint,
                    "status": status,
                    "reason": str(getattr(e, "reason", "")),
                    "model": str(self.config.model),
                    "timeout_sec": int(self.config.timeout_sec),
                    "messages": len(payload.get("messages") or []),
                    "tools_mode": "legacy" if use_legacy else "tools",
                    "tools": len(payload.get("tools") or []) if "tools" in payload else 0,
                    "functions": len(payload.get("functions") or []) if "functions" in payload else 0,
                    "error_message": err_message,
                }
                raise ValueError(
                    "openai-compatible request failed: "
                    + json.dumps(summary, ensure_ascii=False)
                    + f" response_body={_truncate(err_body, 4000)}"
                ) from None

            except URLError as e:
                if attempt < max_attempts:
                    _backoff_sleep(attempt)
                    continue
                summary = {
                    "endpoint": endpoint,
                    "reason": str(getattr(e, "reason", e)),
                    "model": str(self.config.model),
                    "timeout_sec": int(self.config.timeout_sec),
                    "tools_mode": "legacy" if use_legacy else "tools",
                }
                raise ValueError(
                    "openai-compatible request failed: " + json.dumps(summary, ensure_ascii=False)
                ) from None

        raise ValueError("openai-compatible request failed: exhausted retries")
