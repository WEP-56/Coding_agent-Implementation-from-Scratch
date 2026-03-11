from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from codinggirl.core.contracts import Event, ToolCall, ToolResult, utc_now_iso
from codinggirl.runtime.storage_sqlite import SQLiteStore
from codinggirl.runtime.tools.registry import ToolRegistry
from codinggirl.runtime.tools.schema_validation import SchemaValidationError, validate_object


class ToolDenied(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ToolRunner:
    registry: ToolRegistry
    store: SQLiteStore
    run_id: str
    step_id: str | None = None
    allow_tools: set[str] | None = None
    replay_only: bool = False

    def _allowed(self, tool_name: str) -> bool:
        if self.allow_tools is None:
            return True
        return tool_name in self.allow_tools

    def call(self, tool_name: str, args: dict[str, Any], *, call_id: str | None = None) -> ToolResult:
        if not self._allowed(tool_name):
            raise ToolDenied(f"tool not allowed: {tool_name}")

        # In replay mode, the caller must provide a stable call_id
        if call_id is None:
            call_id = uuid.uuid4().hex

        # Validate tool args at the runner boundary so handlers can assume well-formed input.
        spec = self.registry.get_spec(tool_name)
        try:
            validated = validate_object(spec.input_schema, dict(args)).value
        except SchemaValidationError as e:
            validated = None
            validation_error = str(e)
        else:
            validation_error = None

        call = ToolCall(call_id=call_id, tool_name=tool_name, args=validated if isinstance(validated, dict) else dict(args))

        if self.replay_only:
            out = self.store.get_tool_call_output(call.call_id)
            if out is None:
                res = ToolResult(
                    call_id=call.call_id,
                    tool_name=tool_name,
                    ok=False,
                    error="replay_only: missing recorded output",
                )
            else:
                res = ToolResult(call_id=call.call_id, tool_name=tool_name, ok=True, content=out)
            # Do not mutate tool_call/event tables in replay-only mode.
            return res

        self.store.record_tool_call_start(
            call_id=call.call_id,
            run_id=self.run_id,
            step_id=self.step_id,
            tool_name=tool_name,
            created_at=call.created_at,
            input_payload={"args": call.args},
        )
        self.store.append_event(
            run_id=self.run_id,
            step_id=self.step_id,
            kind="tool_call",
            ts=utc_now_iso(),
            payload={"call_id": call.call_id, "tool": tool_name, "args": call.args},
        )

        if validation_error is not None:
            res = ToolResult(call_id=call.call_id, tool_name=tool_name, ok=False, error=f"invalid args: {validation_error}")
        else:
            handler = self.registry.get_handler(tool_name)
            try:
                res = handler(call)
            except Exception as e:  # noqa: BLE001
                res = ToolResult(call_id=call.call_id, tool_name=tool_name, ok=False, error=str(e))

        self.store.record_tool_call_finish(
            call_id=call.call_id,
            completed_at=res.completed_at,
            ok=res.ok,
            output_payload={"content": res.content, "stdout": res.stdout, "stderr": res.stderr}
            if res.ok
            else None,
            error_payload={"error": res.error} if not res.ok else None,
        )
        self.store.append_event(
            run_id=self.run_id,
            step_id=self.step_id,
            kind="tool_result",
            ts=utc_now_iso(),
            payload={"call_id": res.call_id, "tool": tool_name, "ok": res.ok, "error": res.error},
        )
        return res
