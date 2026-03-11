from __future__ import annotations

import sqlite3
from dataclasses import asdict
from pathlib import Path

from codinggirl.core.contracts import ToolCall, ToolResult
from codinggirl.runtime.indexer.manifest import load_manifest, save_manifest, scan_manifest
from codinggirl.runtime.indexer.repo_map import build_repo_map_items, query_repo_map_items, render_repo_map
from codinggirl.runtime.indexer.symbols import index_changed_source_files, open_symbols_db
from codinggirl.runtime.workspace import RepoWorkspace


def make_index_query_repo_map(workspace: RepoWorkspace):
    def handler(call: ToolCall) -> ToolResult:
        db_path = str(call.args.get("db_path", ".codinggirl/index/symbols.sqlite"))
        focus_terms_arg = call.args.get("focus_terms") or []
        focus_terms = {str(x).strip().lower() for x in focus_terms_arg if str(x).strip()}
        path_query = call.args.get("path_query")
        name_query = call.args.get("name_query")
        kinds_arg = call.args.get("kinds")
        kinds = [str(x) for x in kinds_arg] if isinstance(kinds_arg, list) else None
        max_results = int(call.args.get("max_results", 200))
        include_tests = bool(call.args.get("include_tests", False))
        group_by = str(call.args.get("group_by", "path"))
        with_snippets = bool(call.args.get("with_snippets", False))
        snippet_lines = int(call.args.get("snippet_lines", 12))
        snippet_before = int(call.args.get("snippet_before", 0))
        max_snippets = int(call.args.get("max_snippets", 50))

        if max_results <= 0:
            max_results = 1
        if max_results > 2000:
            max_results = 2000
        if group_by not in ("path", "kind"):
            raise RuntimeError("group_by must be 'path' or 'kind'")
        if snippet_lines <= 0:
            snippet_lines = 1
        if snippet_lines > 80:
            snippet_lines = 80
        if snippet_before < 0:
            snippet_before = 0
        if snippet_before > 200:
            snippet_before = 200
        if max_snippets <= 0:
            max_snippets = 0
        if max_snippets > 200:
            max_snippets = 200

        p = workspace.resolve_path(db_path)
        if not p.exists():
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                ok=False,
                error=f"symbols db not found: {db_path}",
            )

        conn = sqlite3.connect(p)
        conn.row_factory = sqlite3.Row
        try:
            items = query_repo_map_items(
                conn,
                focus_terms=focus_terms,
                path_query=str(path_query) if path_query else None,
                name_query=str(name_query) if name_query else None,
                kinds=kinds,
                include_tests=include_tests,
                max_results=max_results,
            )
        finally:
            conn.close()

        groups: dict[str, list[dict[str, object]]] = {}
        snippets_included = 0
        for it in items:
            key = it.path if group_by == "path" else it.kind
            item_dict = asdict(it)
            if with_snippets and snippets_included < max_snippets:
                try:
                    start_line = max(1, int(it.line_start) - snippet_before)
                    snippet = workspace.read_text_range(
                        it.path,
                        start_line=start_line,
                        max_lines=snippet_lines,
                        max_bytes=80_000,
                    )
                    item_dict["snippet"] = {
                        "start_line": snippet.get("start_line"),
                        "end_line": snippet.get("end_line"),
                        "text": snippet.get("text"),
                        "truncated": snippet.get("truncated"),
                    }
                    snippets_included += 1
                except Exception as e:  # noqa: BLE001
                    item_dict["snippet_error"] = str(e)
                    snippets_included += 1

            groups.setdefault(key, []).append(item_dict)

        grouped = [
            {"key": k, "items": groups[k]}
            for k in sorted(groups.keys(), key=lambda x: (x.lower(), x))
        ]

        return ToolResult(
            call_id=call.call_id,
            tool_name=call.tool_name,
            ok=True,
            content={
                "db_path": db_path,
                "group_by": group_by,
                "filters": {
                    "focus_terms": sorted(focus_terms),
                    "path_query": path_query,
                    "name_query": name_query,
                    "kinds": kinds,
                    "include_tests": include_tests,
                    "max_results": max_results,
                    "with_snippets": with_snippets,
                    "snippet_lines": snippet_lines,
                    "snippet_before": snippet_before,
                    "max_snippets": max_snippets,
                },
                "groups": grouped,
                "returned": len(items),
                "snippets_included": snippets_included,
            },
        )

    return handler


def make_index_build(workspace: RepoWorkspace):
    def handler(call: ToolCall) -> ToolResult:
        index_dir = str(call.args.get("index_dir", ".codinggirl/index"))
        max_file_size = int(call.args.get("max_file_size", 1_000_000))
        max_repo_map_lines = int(call.args.get("max_repo_map_lines", 300))
        use_default_ignore = bool(call.args.get("use_default_ignore", True))
        ignore_arg = call.args.get("ignore")
        ignore: list[str] = [str(x) for x in ignore_arg] if isinstance(ignore_arg, list) else ([str(ignore_arg)] if ignore_arg else [])
        focus_terms_arg = call.args.get("focus_terms") or []
        focus_terms = {str(x).strip().lower() for x in focus_terms_arg if str(x).strip()}

        if max_file_size <= 0:
            max_file_size = 1
        if max_repo_map_lines <= 0:
            max_repo_map_lines = 1
        if max_repo_map_lines > 2000:
            max_repo_map_lines = 2000

        index_dir_path = workspace.resolve_path(index_dir)
        index_dir_path.mkdir(parents=True, exist_ok=True)

        manifest_path = index_dir_path / "manifest.json"
        symbols_path = index_dir_path / "symbols.sqlite"
        repo_map_path = index_dir_path / "repo_map.txt"

        prev = load_manifest(manifest_path)
        entries, added, changed, removed = scan_manifest(
            workspace,
            previous=prev,
            max_file_size=max_file_size,
            ignore=ignore,
            use_default_ignore=use_default_ignore,
        )
        save_manifest(manifest_path, entries)

        changed_all = sorted(set(added + changed))
        conn = open_symbols_db(symbols_path)
        try:
            index_changed_source_files(
                workspace,
                conn=conn,
                changed_files=changed_all,
                removed_files=removed,
                max_bytes=max_file_size,
            )
            items = build_repo_map_items(conn, focus_terms=focus_terms)
        finally:
            conn.close()

        repo_map_path.write_text(render_repo_map(items, max_lines=max_repo_map_lines), encoding="utf-8")

        # Return paths relative to repo root
        rel_manifest = str(Path(index_dir) / "manifest.json")
        rel_symbols = str(Path(index_dir) / "symbols.sqlite")
        rel_repo_map = str(Path(index_dir) / "repo_map.txt")

        return ToolResult(
            call_id=call.call_id,
            tool_name=call.tool_name,
            ok=True,
            content={
                "index_dir": index_dir,
                "manifest": rel_manifest.replace("\\", "/"),
                "symbols_db": rel_symbols.replace("\\", "/"),
                "repo_map": rel_repo_map.replace("\\", "/"),
                "added": len(added),
                "changed": len(changed),
                "removed": len(removed),
                "indexed_changed_files": len(changed_all),
                "focus_terms": sorted(focus_terms),
            },
        )

    return handler


def make_index_query_imports(workspace: RepoWorkspace):
    def handler(call: ToolCall) -> ToolResult:
        db_path = str(call.args.get("db_path", ".codinggirl/index/symbols.sqlite"))
        path_query = call.args.get("path_query")
        module_query = call.args.get("module_query")
        include_tests = bool(call.args.get("include_tests", False))
        group_by = str(call.args.get("group_by", "path"))
        max_results = int(call.args.get("max_results", 500))

        if group_by not in ("path", "module"):
            raise RuntimeError("group_by must be 'path' or 'module'")
        if max_results <= 0:
            max_results = 1
        if max_results > 5000:
            max_results = 5000

        p = workspace.resolve_path(db_path)
        if not p.exists():
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                ok=False,
                error=f"symbols db not found: {db_path}",
            )

        conn = sqlite3.connect(p)
        conn.row_factory = sqlite3.Row
        try:
            clauses: list[str] = []
            params: list[object] = []
            if not include_tests:
                clauses.append("path NOT LIKE 'tests/%'")
            if path_query:
                clauses.append("path LIKE ?")
                params.append(f"%{path_query}%")
            if module_query:
                clauses.append("module LIKE ?")
                params.append(f"%{module_query}%")

            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            sql = f"SELECT path, module, line FROM import_edge{where} ORDER BY path, line LIMIT ?"
            rows = conn.execute(sql, [*params, max_results]).fetchall()
        finally:
            conn.close()

        records: list[dict[str, object]] = []
        for r in rows:
            records.append(
                {
                    "path": str(r["path"]),
                    "module": str(r["module"]),
                    "line": int(r["line"]),
                }
            )

        groups: dict[str, list[dict[str, object]]] = {}
        for rec in records:
            key = str(rec[group_by])
            groups.setdefault(key, []).append(rec)

        grouped = [
            {"key": k, "items": groups[k], "count": len(groups[k])}
            for k in sorted(groups.keys(), key=lambda x: (x.lower(), x))
        ]

        return ToolResult(
            call_id=call.call_id,
            tool_name=call.tool_name,
            ok=True,
            content={
                "db_path": db_path,
                "group_by": group_by,
                "filters": {
                    "path_query": path_query,
                    "module_query": module_query,
                    "include_tests": include_tests,
                    "max_results": max_results,
                },
                "groups": grouped,
                "returned": len(records),
            },
        )

    return handler
