from __future__ import annotations

from codinggirl.runtime.tools.builtins_fs import (
    make_fs_glob,
    make_fs_insert_at_line,
    make_fs_list_dir,
    make_fs_read_file,
    make_fs_read_range,
    make_fs_replace_text,
    make_fs_write_file,
)
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
        ),
        make_fs_list_dir(workspace),
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
                },
                "required": ["pattern"],
                "additionalProperties": False,
            },
            risk_level="low",
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
        ),
        make_fs_insert_at_line(workspace),
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
        ),
        make_patch_apply_unified_diff(workspace),
    )

    return reg
