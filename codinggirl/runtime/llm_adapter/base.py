from __future__ import annotations

from typing import Protocol

from codinggirl.runtime.llm_adapter.models import ChatMessage, LLMResponse, ToolSchema


class LLMProvider(Protocol):
    def chat(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[ToolSchema] | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        ...
