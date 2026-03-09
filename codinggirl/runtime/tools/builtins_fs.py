from __future__ import annotations

from typing import Any

from codinggirl.core.contracts import ToolCall, ToolResult
from codinggirl.runtime.workspace import RepoWorkspace


def make_fs_list_dir(workspace: RepoWorkspace):
    def handler(call: ToolCall) -> ToolResult:
        path = str(call.args.get("path", "."))
        items = workspace.list_dir(path)
        return ToolResult(call_id=call.call_id, tool_name=call.tool_name, ok=True, content={"items": items})

    return handler


def make_fs_read_file(workspace: RepoWorkspace):
    def handler(call: ToolCall) -> ToolResult:
        path = str(call.args["path"])
        text = workspace.read_text(path)
        return ToolResult(call_id=call.call_id, tool_name=call.tool_name, ok=True, content={"path": path, "text": text})

    return handler
