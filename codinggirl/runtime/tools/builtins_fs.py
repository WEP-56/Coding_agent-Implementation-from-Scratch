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


def make_fs_list_files(workspace: RepoWorkspace):
    def handler(call: ToolCall) -> ToolResult:
        path = str(call.args.get("path", "."))
        recursive = bool(call.args.get("recursive", True))
        include_dirs = bool(call.args.get("include_dirs", False))
        ignore_arg = call.args.get("ignore")
        ignore: list[str] = [str(x) for x in ignore_arg] if isinstance(ignore_arg, list) else ([str(ignore_arg)] if ignore_arg else [])
        use_default_ignore = bool(call.args.get("use_default_ignore", True))
        if use_default_ignore:
            ignore = list(dict.fromkeys(workspace.default_ignore_patterns() + ignore))
        max_results = int(call.args.get("max_results", 20_000))
        if max_results <= 0:
            max_results = 1

        items = workspace.list_files(
            path,
            recursive=recursive,
            include_dirs=include_dirs,
            ignore=ignore,
            max_results=max_results,
        )
        return ToolResult(
            call_id=call.call_id,
            tool_name=call.tool_name,
            ok=True,
            content={"path": path, "recursive": recursive, "include_dirs": include_dirs, "items": items},
        )

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
        ignore_arg = call.args.get("ignore")
        ignore: list[str] = [str(x) for x in ignore_arg] if isinstance(ignore_arg, list) else ([str(ignore_arg)] if ignore_arg else [])
        use_default_ignore = bool(call.args.get("use_default_ignore", True))
        if use_default_ignore:
            ignore = list(dict.fromkeys(workspace.default_ignore_patterns() + ignore))
        items = workspace.glob(pattern, path=path, recursive=recursive, include_dirs=include_dirs, ignore=ignore)
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


def make_fs_read_many_files(workspace: RepoWorkspace):
    def handler(call: ToolCall) -> ToolResult:
        items_arg = call.args.get("items")
        if not isinstance(items_arg, list):
            raise RuntimeError("items must be an array")

        max_total_bytes = int(call.args.get("max_total_bytes", 2_000_000))
        if max_total_bytes <= 0:
            max_total_bytes = 1

        out: list[dict[str, object]] = []
        used = 0

        for raw in items_arg:
            if not isinstance(raw, dict):
                raise RuntimeError("each item must be an object")
            path = str(raw["path"])
            start_line = raw.get("start_line")
            end_line = raw.get("end_line")
            offset = raw.get("offset")
            limit = raw.get("limit")
            max_lines = raw.get("max_lines")
            max_bytes = raw.get("max_bytes")

            try:
                content = workspace.read_text_range(
                    path,
                    start_line=int(start_line) if start_line is not None else None,
                    end_line=int(end_line) if end_line is not None else None,
                    offset=int(offset) if offset is not None else None,
                    limit=int(limit) if limit is not None else None,
                    max_lines=int(max_lines) if max_lines is not None else None,
                    max_bytes=int(max_bytes) if max_bytes is not None else 512_000,
                )
                text = str(content.get("text", ""))
                used += len(text.encode("utf-8", errors="replace"))
                out.append(content)
            except Exception as e:  # noqa: BLE001
                out.append({"path": path, "ok": False, "error": str(e)})

            if used >= max_total_bytes:
                break

        return ToolResult(
            call_id=call.call_id,
            tool_name=call.tool_name,
            ok=True,
            content={"items": out, "truncated": used >= max_total_bytes, "max_total_bytes": max_total_bytes},
        )

    return handler
