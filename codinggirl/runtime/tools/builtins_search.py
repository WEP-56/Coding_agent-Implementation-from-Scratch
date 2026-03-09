from __future__ import annotations

import re
import subprocess
from pathlib import Path
from shutil import which

from codinggirl.core.contracts import ToolCall, ToolResult
from codinggirl.runtime.workspace import RepoWorkspace


def _search_fallback(root: Path, pattern: str, *, max_results: int) -> list[dict[str, object]]:
    regex = re.compile(pattern)
    results: list[dict[str, object]] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.stat().st_size > 512_000:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            if regex.search(line):
                results.append({"path": str(p.relative_to(root)).replace("\\", "/"), "line": i, "text": line})
                if len(results) >= max_results:
                    return results
    return results


def make_search_rg(workspace: RepoWorkspace):
    def handler(call: ToolCall) -> ToolResult:
        pattern = str(call.args["pattern"])
        max_results = int(call.args.get("max_results", 50))
        if max_results <= 0:
            max_results = 1

        rg = which("rg")
        if rg:
            try:
                proc = subprocess.run(
                    [rg, "--line-number", "--no-heading", "--hidden", "--glob", "!**/.git/**", pattern, str(workspace.root)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            except OSError:
                proc = None
            if proc is None:
                out = _search_fallback(workspace.root, pattern, max_results=max_results)
                return ToolResult(call_id=call.call_id, tool_name=call.tool_name, ok=True, content={"results": out, "engine": "python"})
            if proc.returncode not in (0, 1):
                return ToolResult(call_id=call.call_id, tool_name=call.tool_name, ok=False, stderr=proc.stderr, error="rg failed")
            out: list[dict[str, object]] = []
            for line in proc.stdout.splitlines():
                # format: path:line:text
                parts = line.split(":", 2)
                if len(parts) != 3:
                    continue
                path_s, line_s, text = parts
                rel = str(Path(path_s).resolve(strict=False).relative_to(workspace.root)).replace("\\", "/")
                out.append({"path": rel, "line": int(line_s), "text": text})
                if len(out) >= max_results:
                    break
            return ToolResult(call_id=call.call_id, tool_name=call.tool_name, ok=True, content={"results": out, "engine": "rg"})

        out = _search_fallback(workspace.root, pattern, max_results=max_results)
        return ToolResult(call_id=call.call_id, tool_name=call.tool_name, ok=True, content={"results": out, "engine": "python"})

    return handler
