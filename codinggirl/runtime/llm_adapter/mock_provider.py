from __future__ import annotations

import json
from dataclasses import dataclass, field

from codinggirl.runtime.llm_adapter.models import ChatMessage, LLMConfig, LLMResponse, ToolCall, ToolSchema


@dataclass
class MockProvider:
    """
    Mock LLM Provider for testing

    Supports two modes:
    1. Deterministic mode: responds based on user input patterns
    2. Scripted mode: returns pre-configured responses in sequence
    """
    config: LLMConfig
    _responses: list[LLMResponse] = field(default_factory=list, init=False)
    _response_index: int = field(default=0, init=False)

    def set_next_response(self, response: LLMResponse) -> None:
        """Set a single response (clears previous responses)"""
        self._responses = [response]
        self._response_index = 0

    def add_response(self, response: LLMResponse) -> None:
        """Add a response to the queue"""
        self._responses.append(response)

    def chat(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[ToolSchema] | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        _ = temperature

        # If we have scripted responses, use them
        if self._responses:
            if self._response_index < len(self._responses):
                response = self._responses[self._response_index]
                self._response_index += 1
                return response
            # If we've exhausted responses, return a default stop response
            return LLMResponse(
                model=self.config.model,
                content="No more scripted responses available.",
                finish_reason="stop",
                tool_calls=[],
                raw={"provider": "mock"},
            )

        # Fallback to deterministic mode
        last_user = ""
        for m in reversed(messages):
            if m.role == "user":
                last_user = m.content
                break

        # deterministic tool-call trigger for tests and local probe
        if tools and last_user.startswith("CALL_TOOL:"):
            t = tools[0]
            tc = ToolCall(
                id="mock-call-1",
                name=t.name,
                arguments_json=json.dumps({"echo": last_user.removeprefix("CALL_TOOL:").strip()}, ensure_ascii=False),
            )
            return LLMResponse(
                model=self.config.model,
                content="",
                finish_reason="tool_calls",
                tool_calls=[tc],
                raw={"provider": "mock"},
            )

        return LLMResponse(
            model=self.config.model,
            content=f"MOCK_ECHO: {last_user}",
            finish_reason="stop",
            tool_calls=[],
            raw={"provider": "mock"},
        )
