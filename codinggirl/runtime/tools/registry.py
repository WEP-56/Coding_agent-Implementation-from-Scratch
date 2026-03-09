from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from codinggirl.core.contracts import ToolCall, ToolResult


ToolHandler = Callable[[ToolCall], ToolResult]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    risk_level: str = "low"


class ToolRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, ToolSpec] = {}
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, spec: ToolSpec, handler: ToolHandler) -> None:
        if spec.name in self._specs:
            raise ValueError(f"tool already registered: {spec.name}")
        self._specs[spec.name] = spec
        self._handlers[spec.name] = handler

    def get_spec(self, name: str) -> ToolSpec:
        return self._specs[name]

    def list_specs(self) -> list[ToolSpec]:
        return [self._specs[k] for k in sorted(self._specs.keys())]

    def get_handler(self, name: str) -> ToolHandler:
        return self._handlers[name]
