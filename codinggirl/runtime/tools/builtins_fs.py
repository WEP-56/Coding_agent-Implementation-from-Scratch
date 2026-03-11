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


def make_fs_read_range(workspace: RepoWorkspace):
    def handler(call: ToolCall) -> ToolResult:
        path = str(call.args["path"])
        content = workspace.read_text_range(
            path,
            start_line=call.args.get("start_line"),
            end_line=call.args.get("end_line"),
            offset=call.args.get("offset"),
            limit=call.args.get("limit"),
            max_lines=call.args.get("max_lines"),
        )
        return ToolResult(call_id=call.call_id, tool_name=call.tool_name, ok=True, content=content)

    return handler


def make_fs_glob(workspace: RepoWorkspace):
    def handler(call: ToolCall) -> ToolResult:
        pattern = str(call.args["pattern"])
        path = str(call.args.get("path", "."))
        recursive = bool(call.args.get("recursive", True))
        include_dirs = bool(call.args.get("include_dirs", False))
        items = workspace.glob(pattern, path=path, recursive=recursive, include_dirs=include_dirs)
        return ToolResult(
            call_id=call.call_id,
            tool_name=call.tool_name,
            ok=True,
            content={"path": path, "pattern": pattern, "items": items},
        )

    return handler


def make_fs_replace_text(workspace: RepoWorkspace):
    def handler(call: ToolCall) -> ToolResult:
        path = str(call.args["path"])
        result = workspace.replace_text(
            path,
            old_text=str(call.args["old_text"]),
            new_text=str(call.args.get("new_text", "")),
            expected_occurrences=call.args.get("expected_occurrences"),
            must_contain=call.args.get("must_contain"),
        )
        return ToolResult(call_id=call.call_id, tool_name=call.tool_name, ok=True, content=result)

    return handler


def make_fs_write_file(workspace: RepoWorkspace):
    def handler(call: ToolCall) -> ToolResult:
        path = str(call.args["path"])
        text = str(call.args["text"])
        must_not_exist = bool(call.args.get("must_not_exist", False))
        if must_not_exist:
            p = workspace.resolve_path(path)
            if p.exists():
                raise RuntimeError(f"file already exists: {path}")
        workspace.write_text(path, text)
        return ToolResult(call_id=call.call_id, tool_name=call.tool_name, ok=True, content={"path": path})

    return handler


def make_fs_insert_at_line(workspace: RepoWorkspace):
    def handler(call: ToolCall) -> ToolResult:
        path = str(call.args["path"])
        line = int(call.args["line"])
        text = str(call.args["text"])
        result = workspace.insert_text_at_line(path, line=line, text=text)
        return ToolResult(call_id=call.call_id, tool_name=call.tool_name, ok=True, content=result)

    return handler
