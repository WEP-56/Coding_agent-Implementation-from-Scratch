from __future__ import annotations

import json
from dataclasses import dataclass

from codinggirl.runtime.llm_adapter.models import ChatMessage, LLMConfig, LLMResponse, ToolCall, ToolSchema


@dataclass(frozen=True, slots=True)
class MockProvider:
    config: LLMConfig

    def chat(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[ToolSchema] | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        _ = temperature
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
