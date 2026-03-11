from __future__ import annotations

from dataclasses import dataclass

from codinggirl.core.contracts import ToolCall, ToolResult
from codinggirl.runtime.tools.registry import ToolSpec


@dataclass(frozen=True, slots=True)
class ToolHookContext:
    run_id: str
    step_id: str | None
    spec: ToolSpec | None
    call: ToolCall


class ToolHook:
    def pre_tool_use(self, ctx: ToolHookContext) -> None:  # noqa: B027
        return

    def post_tool_use(self, ctx: ToolHookContext, result: ToolResult) -> None:  # noqa: B027
        return

    def post_tool_use_failure(self, ctx: ToolHookContext, result: ToolResult) -> None:  # noqa: B027
        return

