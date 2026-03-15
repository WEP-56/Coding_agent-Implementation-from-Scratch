from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from codinggirl.core.contracts import ToolCall, ToolResult, utc_now_iso
from codinggirl.core.policy import PermissionPolicy
from codinggirl.runtime.storage_sqlite import SQLiteStore
from codinggirl.runtime.tools.hooks import ToolHook, ToolHookContext
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
    permission: PermissionPolicy | None = None
    hooks: list[ToolHook] | None = None

    def _allowed(self, tool_name: str) -> bool:
        if self.allow_tools is None:
            return True
        return tool_name in self.allow_tools

    def call(self, tool_name: str, args: dict[str, Any], *, call_id: str | None = None) -> ToolResult:
        # In replay mode, the caller must provide a stable call_id
        if call_id is None:
            call_id = uuid.uuid4().hex

        spec = None
        spec_error = None
        try:
            spec = self.registry.get_spec(tool_name)
        except KeyError:
            spec_error = f"unknown tool: {tool_name}"

        validated_args: dict[str, Any] = dict(args)
        validated: Any = None
        validation_error: str | None = None

        if spec is not None:
            try:
                validated = validate_object(spec.input_schema, dict(args)).value
            except SchemaValidationError as e:
                validation_error = str(e)

        if isinstance(validated, dict):
            validated_args = validated

        risk_level = str(spec.risk_level) if spec else "low"
        call = ToolCall(
            call_id=call_id,
            tool_name=tool_name,
            args=validated_args,
            risk_level=risk_level,  # type: ignore[arg-type]
        )
        hook_ctx = ToolHookContext(run_id=self.run_id, step_id=self.step_id, spec=spec, call=call)

        if self.replay_only:
            return self._replay_result(hook_ctx)

        self.store.record_tool_call_start(
            call_id=call.call_id,
            run_id=self.run_id,
            step_id=self.step_id,
            tool_name=tool_name,
            created_at=call.created_at,
            input_payload={
                "args": call.args,
                "risk_level": call.risk_level,
                "required_permission": str(spec.required_permission) if spec else "read",
                "permission_mode": self.permission.mode if self.permission else None,
            },
        )
        self.store.append_event(
            run_id=self.run_id,
            step_id=self.step_id,
            kind="tool_call",
            ts=utc_now_iso(),
            payload={
                "call_id": call.call_id,
                "tool": tool_name,
                "args": call.args,
                "risk_level": call.risk_level,
                "required_permission": str(spec.required_permission) if spec else "read",
                "permission_mode": self.permission.mode if self.permission else None,
            },
        )

        if spec_error is not None:
            res = ToolResult(call_id=call.call_id, tool_name=tool_name, ok=False, error=spec_error)
        elif not self._allowed(tool_name):
            res = ToolResult(call_id=call.call_id, tool_name=tool_name, ok=False, error=f"tool not allowed: {tool_name}")
        elif validation_error is not None:
            res = ToolResult(call_id=call.call_id, tool_name=tool_name, ok=False, error=f"invalid args: {validation_error}")
        else:
            if self.permission and spec:
                try:
                    if spec.required_permission == "write":
                        self.permission.require_write()
                    elif spec.required_permission == "exec":
                        self.permission.require_exec()
                except PermissionError as e:
                    res = ToolResult(call_id=call.call_id, tool_name=tool_name, ok=False, error=str(e))
                else:
                    res = self._invoke_handler_with_hooks(hook_ctx)
            else:
                res = self._invoke_handler_with_hooks(hook_ctx)

        self.store.record_tool_call_finish(
            call_id=call.call_id,
            completed_at=res.completed_at,
            ok=res.ok,
            output_payload={"content": res.content, "stdout": res.stdout, "stderr": res.stderr},
            error_payload={"error": res.error} if not res.ok else None,
        )
        self.store.append_event(
            run_id=self.run_id,
            step_id=self.step_id,
            kind="tool_result",
            ts=utc_now_iso(),
            payload={
                "call_id": res.call_id,
                "tool": tool_name,
                "ok": res.ok,
                "error": res.error,
                "risk_level": call.risk_level,
                "required_permission": str(spec.required_permission) if spec else "read",
                "permission_mode": self.permission.mode if self.permission else None,
            },
        )
        return res

    def _replay_result(self, ctx: ToolHookContext) -> ToolResult:
        rec = self.store.get_tool_call_record(ctx.call.call_id)
        if rec is None:
            return ToolResult(
                call_id=ctx.call.call_id,
                tool_name=ctx.call.tool_name,
                ok=False,
                error="replay_only: missing recorded output",
            )
        status = str(rec.get("status", ""))
        out = rec.get("output") or {}
        err = rec.get("error") or {}
        if status == "success":
            return ToolResult(
                call_id=ctx.call.call_id,
                tool_name=ctx.call.tool_name,
                ok=True,
                content=out.get("content"),
                stdout=out.get("stdout"),
                stderr=out.get("stderr"),
            )
        if status == "error":
            return ToolResult(
                call_id=ctx.call.call_id,
                tool_name=ctx.call.tool_name,
                ok=False,
                content=out.get("content"),
                stdout=out.get("stdout"),
                stderr=out.get("stderr"),
                error=str(err.get("error") or "error"),
            )
        return ToolResult(
            call_id=ctx.call.call_id,
            tool_name=ctx.call.tool_name,
            ok=False,
            error=f"replay_only: unknown status: {status}",
        )

    def _invoke_handler_with_hooks(self, ctx: ToolHookContext) -> ToolResult:
        for hook in self.hooks or []:
            try:
                hook.pre_tool_use(ctx)
            except Exception as e:  # noqa: BLE001
                self.store.append_event(
                    run_id=self.run_id,
                    step_id=self.step_id,
                    kind="hook_error",
                    ts=utc_now_iso(),
                    payload={
                        "call_id": ctx.call.call_id,
                        "stage": "pre_tool_use",
                        "hook": type(hook).__name__,
                        "error": str(e),
                    },
                )
                return ToolResult(call_id=ctx.call.call_id, tool_name=ctx.call.tool_name, ok=False, error=str(e))

        handler = self.registry.get_handler(ctx.call.tool_name)
        try:
            res = handler(ctx.call)
        except Exception as e:  # noqa: BLE001
            res = ToolResult(call_id=ctx.call.call_id, tool_name=ctx.call.tool_name, ok=False, error=str(e))

        for hook in self.hooks or []:
            try:
                if res.ok:
                    hook.post_tool_use(ctx, res)
                else:
                    hook.post_tool_use_failure(ctx, res)
            except Exception as e:  # noqa: BLE001
                self.store.append_event(
                    run_id=self.run_id,
                    step_id=self.step_id,
                    kind="hook_error",
                    ts=utc_now_iso(),
                    payload={
                        "call_id": ctx.call.call_id,
                        "stage": "post_tool_use" if res.ok else "post_tool_use_failure",
                        "hook": type(hook).__name__,
                        "error": str(e),
                    },
                )

        return res
