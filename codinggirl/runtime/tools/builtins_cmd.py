from __future__ import annotations

import subprocess

from codinggirl.core.contracts import ToolCall, ToolResult
from codinggirl.runtime.workspace import RepoWorkspace


def _truncate_utf8(text: str, max_bytes: int) -> tuple[str, bool]:
    if max_bytes <= 0:
        return "", True
    data = text.encode("utf-8", errors="replace")
    if len(data) <= max_bytes:
        return text, False
    trimmed = data[:max_bytes]
    while True:
        try:
            return trimmed.decode("utf-8", errors="strict"), True
        except UnicodeDecodeError:
            if not trimmed:
                return "", True
            trimmed = trimmed[:-1]


def make_cmd_run(workspace: RepoWorkspace):
    def handler(call: ToolCall) -> ToolResult:
        command = str(call.args["command"])
        cwd = str(call.args.get("cwd", "."))
        timeout_ms = int(call.args.get("timeout_ms", call.timeout_ms))
        max_output_bytes = int(call.args.get("max_output_bytes", 200_000))

        if timeout_ms <= 0:
            timeout_ms = 1
        if timeout_ms > 600_000:
            timeout_ms = 600_000
        if max_output_bytes <= 0:
            max_output_bytes = 1
        if max_output_bytes > 5_000_000:
            max_output_bytes = 5_000_000

        cwd_path = workspace.resolve_path(cwd)

        try:
            proc = subprocess.run(
                command,
                cwd=str(cwd_path),
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_ms / 1000.0,
            )
        except subprocess.TimeoutExpired as e:
            stdout, _ = _truncate_utf8((e.stdout or ""), max_output_bytes)
            stderr, _ = _truncate_utf8((e.stderr or ""), max_output_bytes)
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                ok=False,
                content={"command": command, "cwd": cwd, "timeout_ms": timeout_ms, "exit_code": None},
                stdout=stdout,
                stderr=stderr,
                error="command timed out",
            )
        except Exception as e:  # noqa: BLE001
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                ok=False,
                content={"command": command, "cwd": cwd, "timeout_ms": timeout_ms, "exit_code": None},
                error=str(e),
            )

        stdout, stdout_truncated = _truncate_utf8(proc.stdout or "", max_output_bytes)
        stderr, stderr_truncated = _truncate_utf8(proc.stderr or "", max_output_bytes)
        truncated = stdout_truncated or stderr_truncated

        ok = proc.returncode == 0
        return ToolResult(
            call_id=call.call_id,
            tool_name=call.tool_name,
            ok=ok,
            content={
                "command": command,
                "cwd": cwd,
                "timeout_ms": timeout_ms,
                "exit_code": proc.returncode,
                "truncated": truncated,
                "max_output_bytes": max_output_bytes,
            },
            stdout=stdout,
            stderr=stderr,
            error=None if ok else f"exit code {proc.returncode}",
        )

    return handler

