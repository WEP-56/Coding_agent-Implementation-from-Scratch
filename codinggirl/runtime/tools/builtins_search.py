from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from shutil import which

from codinggirl.core.contracts import ToolCall, ToolResult
from codinggirl.runtime.workspace import RepoWorkspace


def _compile_pattern(pattern: str, *, literal: bool, case_sensitive: bool) -> re.Pattern[str]:
    flags = 0 if case_sensitive else re.IGNORECASE
    source = re.escape(pattern) if literal else pattern
    return re.compile(source, flags)


def _matches_globs(path_text: str, patterns: list[str]) -> bool:
    from fnmatch import fnmatchcase

    normalized = path_text.replace("\\", "/")
    return any(fnmatchcase(normalized, pattern.replace("\\", "/")) for pattern in patterns)


def _search_fallback(
    root: Path,
    pattern: str,
    *,
    search_path: str,
    include: list[str],
    exclude: list[str],
    literal: bool,
    case_sensitive: bool,
    context_before: int,
    context_after: int,
    max_results: int,
) -> list[dict[str, object]]:
    base = (root / search_path).resolve(strict=False)
    regex = _compile_pattern(pattern, literal=literal, case_sensitive=case_sensitive)
    results: list[dict[str, object]] = []
    include_patterns = include or ["**/*", "*"]

    for p in base.rglob("*"):
        if not p.is_file():
            continue
        rel = str(p.relative_to(root)).replace("\\", "/")
        rel_from_base = str(p.relative_to(base)).replace("\\", "/")
        if include and not (_matches_globs(rel, include_patterns) or _matches_globs(rel_from_base, include_patterns)):
            continue
        if exclude and (_matches_globs(rel, exclude) or _matches_globs(rel_from_base, exclude)):
            continue
        if p.stat().st_size > 512_000:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        lines = text.splitlines()
        for i, line in enumerate(lines, start=1):
            if regex.search(line):
                start = max(1, i - context_before)
                end = min(len(lines), i + context_after)
                results.append(
                    {
                        "path": rel,
                        "line": i,
                        "text": line,
                        "context": lines[start - 1 : end],
                        "context_start_line": start,
                        "context_end_line": end,
                    }
                )
                if len(results) >= max_results:
                    return results
    return results


def make_search_rg(workspace: RepoWorkspace):
    def handler(call: ToolCall) -> ToolResult:
        pattern = str(call.args["pattern"])
        max_results = int(call.args.get("max_results", 50))
        if max_results <= 0:
            max_results = 1

        search_path = str(call.args.get("path", "."))
        include_arg = call.args.get("include")
        exclude_arg = call.args.get("exclude")
        include: list[str] = [str(x) for x in include_arg] if isinstance(include_arg, list) else ([str(include_arg)] if include_arg else [])
        exclude: list[str] = [str(x) for x in exclude_arg] if isinstance(exclude_arg, list) else ([str(exclude_arg)] if exclude_arg else [])
        literal = bool(call.args.get("literal", False))
        case_sensitive = bool(call.args.get("case_sensitive", True))
        context_before = max(0, int(call.args.get("context_before", 0)))
        context_after = max(0, int(call.args.get("context_after", 0)))

        base = workspace.resolve_path(search_path)
        rg = which("rg")
        if rg:
            cmd: list[str] = [rg, "--json", "--hidden", "--glob", "!**/.git/**"]
            if literal:
                cmd.append("--fixed-strings")
            if not case_sensitive:
                cmd.append("--ignore-case")
            if context_before:
                cmd.extend(["--before-context", str(context_before)])
            if context_after:
                cmd.extend(["--after-context", str(context_after)])
            for glob_pattern in include:
                cmd.append("--glob")
                cmd.append(str(glob_pattern))
            for glob_pattern in exclude:
                cmd.append("--glob")
                cmd.append(f"!{glob_pattern}")
            cmd.extend([pattern, str(base)])
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            except OSError:
                proc = None
            if proc is None:
                out = _search_fallback(
                    workspace.root,
                    pattern,
                    search_path=search_path,
                    include=include,
                    exclude=exclude,
                    literal=literal,
                    case_sensitive=case_sensitive,
                    context_before=context_before,
                    context_after=context_after,
                    max_results=max_results,
                )
                return ToolResult(
                    call_id=call.call_id,
                    tool_name=call.tool_name,
                    ok=True,
                    content={"results": out, "engine": "python"},
                )
            if proc.returncode not in (0, 1):
                return ToolResult(call_id=call.call_id, tool_name=call.tool_name, ok=False, stderr=proc.stderr, error="rg failed")

            out: list[dict[str, object]] = []
            for raw in proc.stdout.splitlines():
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if payload.get("type") != "match":
                    continue
                data = payload.get("data", {})
                path_data = data.get("path", {}).get("text")
                line_number = data.get("line_number")
                line_text = data.get("lines", {}).get("text")
                if not isinstance(path_data, str) or not isinstance(line_number, int) or not isinstance(line_text, str):
                    continue
                rel = str(Path(path_data).resolve(strict=False).relative_to(workspace.root)).replace("\\", "/")
                result_item: dict[str, object] = {"path": rel, "line": line_number, "text": line_text.rstrip("\n")}
                if context_before or context_after:
                    range_data = workspace.read_text_range(
                        rel,
                        start_line=max(1, line_number - context_before),
                        end_line=line_number + context_after,
                    )
                    context_lines = str(range_data["text"]).splitlines()
                    result_item["context"] = context_lines
                    result_item["context_start_line"] = range_data["start_line"]
                    result_item["context_end_line"] = range_data["end_line"]
                out.append(result_item)
                if len(out) >= max_results:
                    break

            return ToolResult(call_id=call.call_id, tool_name=call.tool_name, ok=True, content={"results": out, "engine": "rg"})

        out = _search_fallback(
            workspace.root,
            pattern,
            search_path=search_path,
            include=include,
            exclude=exclude,
            literal=literal,
            case_sensitive=case_sensitive,
            context_before=context_before,
            context_after=context_after,
            max_results=max_results,
        )
        return ToolResult(call_id=call.call_id, tool_name=call.tool_name, ok=True, content={"results": out, "engine": "python"})

    return handler
