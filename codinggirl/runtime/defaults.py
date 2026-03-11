from __future__ import annotations

from codinggirl.runtime.tools.builtins_cmd import make_cmd_run
from codinggirl.runtime.tools.builtins_fs import (
    make_fs_glob,
    make_fs_insert_at_line,
    make_fs_list_dir,
    make_fs_list_files,
    make_fs_read_many_files,
    make_fs_read_file,
    make_fs_read_range,
    make_fs_replace_text,
    make_fs_write_file,
)
from codinggirl.runtime.tools.builtins_index import make_index_build, make_index_query_imports, make_index_query_repo_map
from codinggirl.runtime.tools.builtins_patch import make_patch_apply_unified_diff
from codinggirl.runtime.tools.builtins_search import make_search_rg
from codinggirl.runtime.tools.registry import ToolRegistry, ToolSpec
from codinggirl.runtime.workspace import RepoWorkspace


def create_default_registry(workspace: RepoWorkspace) -> ToolRegistry:
    reg = ToolRegistry()

    reg.register(
        ToolSpec(
            name="fs_list_dir",
            description="List directory entries within repo workspace.",
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Relative path"}},
                "required": [],
                "additionalProperties": False,
            },
            risk_level="low",
            required_permission="read",
        ),
        make_fs_list_dir(workspace),
    )

    reg.register(
        ToolSpec(
            name="fs_list_files",
            description="List files (optionally recursive) within repo workspace.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Base directory path"},
                    "recursive": {"type": "boolean", "default": True},
                    "include_dirs": {"type": "boolean", "default": False},
                    "use_default_ignore": {"type": "boolean", "default": True},
                    "ignore": {
                        "oneOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}},
                        ]
                    },
                    "max_results": {"type": "integer", "minimum": 1, "maximum": 200_000, "default": 20_000},
                },
                "required": [],
                "additionalProperties": False,
            },
            risk_level="low",
            required_permission="read",
        ),
        make_fs_list_files(workspace),
    )

    reg.register(
        ToolSpec(
            name="fs_read_file",
            description="Read a UTF-8 text file within repo workspace.",
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Relative file path"}},
                "required": ["path"],
                "additionalProperties": False,
            },
            risk_level="low",
            required_permission="read",
        ),
        make_fs_read_file(workspace),
    )

    reg.register(
        ToolSpec(
            name="fs_read_range",
            description="Read a line range from a UTF-8 text file within repo workspace.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path"},
                    "start_line": {"type": "integer", "minimum": 1},
                    "end_line": {"type": "integer", "minimum": 1},
                    "offset": {"type": "integer", "minimum": 0},
                    "limit": {"type": "integer", "minimum": 0},
                    "max_lines": {"type": "integer", "minimum": 0},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            risk_level="low",
            required_permission="read",
        ),
        make_fs_read_range(workspace),
    )

    reg.register(
        ToolSpec(
            name="fs_glob",
            description="Find files by glob pattern within repo workspace.",
            input_schema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern"},
                    "path": {"type": "string", "description": "Base directory path"},
                    "recursive": {"type": "boolean", "default": True},
                    "include_dirs": {"type": "boolean", "default": False},
                    "use_default_ignore": {"type": "boolean", "default": True},
                    "ignore": {
                        "oneOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}},
                        ]
                    },
                },
                "required": ["pattern"],
                "additionalProperties": False,
            },
            risk_level="low",
            required_permission="read",
        ),
        make_fs_glob(workspace),
    )

    reg.register(
        ToolSpec(
            name="fs_replace_text",
            description="Replace literal text in a UTF-8 file within repo workspace.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path"},
                    "old_text": {"type": "string", "description": "Exact text to replace"},
                    "new_text": {"type": "string", "description": "Replacement text"},
                    "expected_occurrences": {"type": "integer", "minimum": 0},
                    "must_contain": {
                        "oneOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}},
                        ]
                    },
                },
                "required": ["path", "old_text", "new_text"],
                "additionalProperties": False,
            },
            risk_level="medium",
            required_permission="write",
        ),
        make_fs_replace_text(workspace),
    )

    reg.register(
        ToolSpec(
            name="fs_write_file",
            description="Write a UTF-8 text file within repo workspace.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path"},
                    "text": {"type": "string", "description": "Full file content"},
                    "must_not_exist": {"type": "boolean", "default": False},
                },
                "required": ["path", "text"],
                "additionalProperties": False,
            },
            risk_level="medium",
            required_permission="write",
        ),
        make_fs_write_file(workspace),
    )

    reg.register(
        ToolSpec(
            name="fs_insert_at_line",
            description="Insert text at a 1-based line number within a UTF-8 file in repo workspace.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path"},
                    "line": {"type": "integer", "minimum": 1, "description": "1-based line number"},
                    "text": {"type": "string", "description": "Text to insert"},
                },
                "required": ["path", "line", "text"],
                "additionalProperties": False,
            },
            risk_level="medium",
            required_permission="write",
        ),
        make_fs_insert_at_line(workspace),
    )

    reg.register(
        ToolSpec(
            name="fs_read_many_files",
            description="Read many UTF-8 files (or ranges) within repo workspace in a single call.",
            input_schema={
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string"},
                                "start_line": {"type": "integer", "minimum": 1},
                                "end_line": {"type": "integer", "minimum": 1},
                                "offset": {"type": "integer", "minimum": 0},
                                "limit": {"type": "integer", "minimum": 0},
                                "max_lines": {"type": "integer", "minimum": 0},
                                "max_bytes": {"type": "integer", "minimum": 1},
                            },
                            "required": ["path"],
                            "additionalProperties": False,
                        },
                    },
                    "max_total_bytes": {"type": "integer", "minimum": 1, "default": 2_000_000},
                },
                "required": ["items"],
                "additionalProperties": False,
            },
            risk_level="low",
            required_permission="read",
        ),
        make_fs_read_many_files(workspace),
    )

    reg.register(
        ToolSpec(
            name="search_rg",
            description="Search text in repo using ripgrep if available; fallback otherwise.",
            input_schema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern"},
                    "path": {"type": "string", "description": "Relative search root"},
                    "use_default_ignore": {"type": "boolean", "default": True},
                    "include": {
                        "oneOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}},
                        ]
                    },
                    "exclude": {
                        "oneOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}},
                        ]
                    },
                    "literal": {"type": "boolean", "default": False},
                    "case_sensitive": {"type": "boolean", "default": True},
                    "context_before": {"type": "integer", "minimum": 0},
                    "context_after": {"type": "integer", "minimum": 0},
                    "max_results": {"type": "integer", "minimum": 1, "maximum": 200},
                },
                "required": ["pattern"],
                "additionalProperties": False,
            },
            risk_level="low",
            required_permission="read",
        ),
        make_search_rg(workspace),
    )

    reg.register(
        ToolSpec(
            name="patch_apply_unified_diff",
            description="Apply a unified diff patch to files within workspace (fail on conflict).",
            input_schema={
                "type": "object",
                "properties": {
                    "patch": {"type": "string", "description": "Unified diff"},
                    "allow_delete": {"type": "boolean", "default": False},
                    "backup": {"type": "boolean", "default": True},
                    "backup_dir": {"type": "string", "default": ".codinggirl/backups"},
                    "dry_run": {"type": "boolean", "default": False},
                },
                "required": ["patch"],
                "additionalProperties": False,
            },
            risk_level="medium",
            required_permission="write",
        ),
        make_patch_apply_unified_diff(workspace),
    )

    reg.register(
        ToolSpec(
            name="index_query_repo_map",
            description="Query repo map items from the symbols index database.",
            input_schema={
                "type": "object",
                "properties": {
                    "db_path": {"type": "string", "default": ".codinggirl/index/symbols.sqlite"},
                    "focus_terms": {"type": "array", "items": {"type": "string"}},
                    "path_query": {"type": "string"},
                    "name_query": {"type": "string"},
                    "kinds": {"type": "array", "items": {"type": "string"}},
                    "include_tests": {"type": "boolean", "default": False},
                    "max_results": {"type": "integer", "minimum": 1, "maximum": 2000, "default": 200},
                    "group_by": {"type": "string", "default": "path"},
                    "with_snippets": {"type": "boolean", "default": False},
                    "snippet_lines": {"type": "integer", "minimum": 1, "maximum": 80, "default": 12},
                    "snippet_before": {"type": "integer", "minimum": 0, "maximum": 200, "default": 0},
                    "max_snippets": {"type": "integer", "minimum": 0, "maximum": 200, "default": 50},
                },
                "required": [],
                "additionalProperties": False,
            },
            risk_level="low",
            required_permission="read",
        ),
        make_index_query_repo_map(workspace),
    )

    reg.register(
        ToolSpec(
            name="index_build",
            description="Build (or update) the local symbols index + repo_map under the repo workspace.",
            input_schema={
                "type": "object",
                "properties": {
                    "index_dir": {"type": "string", "default": ".codinggirl/index"},
                    "max_file_size": {"type": "integer", "minimum": 1, "maximum": 5_000_000, "default": 1_000_000},
                    "max_repo_map_lines": {"type": "integer", "minimum": 1, "maximum": 2000, "default": 300},
                    "use_default_ignore": {"type": "boolean", "default": True},
                    "ignore": {
                        "oneOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}},
                        ]
                    },
                    "focus_terms": {"type": "array", "items": {"type": "string"}},
                },
                "required": [],
                "additionalProperties": False,
            },
            risk_level="medium",
            required_permission="write",
        ),
        make_index_build(workspace),
    )

    reg.register(
        ToolSpec(
            name="index_query_imports",
            description="Query import edges from the symbols index database.",
            input_schema={
                "type": "object",
                "properties": {
                    "db_path": {"type": "string", "default": ".codinggirl/index/symbols.sqlite"},
                    "path_query": {"type": "string"},
                    "module_query": {"type": "string"},
                    "include_tests": {"type": "boolean", "default": False},
                    "group_by": {"type": "string", "default": "path"},
                    "max_results": {"type": "integer", "minimum": 1, "maximum": 5000, "default": 500},
                },
                "required": [],
                "additionalProperties": False,
            },
            risk_level="low",
            required_permission="read",
        ),
        make_index_query_imports(workspace),
    )

    reg.register(
        ToolSpec(
            name="cmd_run",
            description="Run a shell command within repo workspace (captures stdout/stderr).",
            input_schema={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command string"},
                    "cwd": {"type": "string", "default": ".", "description": "Relative working directory"},
                    "timeout_ms": {"type": "integer", "minimum": 1, "maximum": 600_000, "default": 120_000},
                    "max_output_bytes": {"type": "integer", "minimum": 1, "maximum": 5_000_000, "default": 200_000},
                },
                "required": ["command"],
                "additionalProperties": False,
            },
            risk_level="high",
            required_permission="exec",
        ),
        make_cmd_run(workspace),
    )

    return reg
