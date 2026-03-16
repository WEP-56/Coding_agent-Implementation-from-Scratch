from __future__ import annotations

import json
import os
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
from codinggirl.runtime.llm_adapter.retry_handler import (
    RetryConfig,
    classify_error,
    calculate_backoff_delay,
)


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def _messages_to_payload_tools(messages: list[ChatMessage]) -> list[dict[str, object]]:
    return _messages_to_payload(messages)


def _messages_to_payload(messages: list[ChatMessage]) -> list[dict[str, object]]:
    """Public test helper: OpenAI tools-mode message mapping."""
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
    return _tools_to_payload(tools)


def _tools_to_payload(tools: list[ToolSchema]) -> list[dict[str, object]]:
    """Public test helper: OpenAI tools-mode tool schema mapping."""
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
        """
        调用 OpenAI 兼容的 API

        使用统一的重试机制，支持自动降级到 legacy function calling
        """
        base_url = self.config.base_url or "https://api.openai.com"
        endpoint = _build_chat_completions_endpoint(base_url)

        api_key = self.config.api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("missing api key (config.api_key or OPENAI_API_KEY)")

        # 配置重试策略
        max_attempts = int(os.environ.get("CODINGGIRL_LLM_MAX_ATTEMPTS", "5") or "5")
        retry_config = RetryConfig(
            max_attempts=max_attempts,
            base_delay=0.5,
            max_delay=16.0,
        )

        use_legacy = False
        last_error = None

        for attempt in range(1, retry_config.max_attempts + 1):
            try:
                # 构建 payload
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

                # 发送请求
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

            except Exception as e:
                last_error = e

                # 分类错误
                error_info = classify_error(e)

                # 处理降级情况（tools 不支持）
                if error_info.should_degrade and tools and not use_legacy:
                    use_legacy = True
                    continue  # 立即重试，不等待

                # 不可重试错误，直接抛出
                if error_info.error_type.value == "non_retryable":
                    self._raise_formatted_error(endpoint, payload, error_info, use_legacy)

                # 最后一次尝试，不再重试
                if attempt >= retry_config.max_attempts:
                    self._raise_formatted_error(endpoint, payload, error_info, use_legacy)

                # 可重试错误，等待后重试
                import time
                delay = calculate_backoff_delay(attempt, retry_config)
                time.sleep(delay)

        # 理论上不会到这里
        if last_error:
            raise last_error
        raise ValueError("openai-compatible request failed: exhausted retries")

    def _raise_formatted_error(
        self,
        endpoint: str,
        payload: dict[str, object],
        error_info: Any,
        use_legacy: bool,
    ) -> None:
        """格式化并抛出错误"""
        summary = {
            "endpoint": endpoint,
            "model": str(self.config.model),
            "timeout_sec": int(self.config.timeout_sec),
            "messages": len(payload.get("messages") or []),
            "tools_mode": "legacy" if use_legacy else "tools",
            "error_type": error_info.error_type.value,
            "error_message": error_info.message,
        }

        if error_info.status_code:
            summary["status"] = error_info.status_code

        raise ValueError(
            "openai-compatible request failed: " + json.dumps(summary, ensure_ascii=False)
        ) from error_info.raw_error
