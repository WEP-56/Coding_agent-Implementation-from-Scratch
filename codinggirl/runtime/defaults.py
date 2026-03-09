from __future__ import annotations

from codinggirl.runtime.tools.builtins_fs import make_fs_list_dir, make_fs_read_file
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
            name="search_rg",
            description="Search text in repo using ripgrep if available; fallback otherwise.",
            input_schema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern"},
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
                },
                "required": ["patch"],
                "additionalProperties": False,
            },
            risk_level="medium",
        ),
        make_patch_apply_unified_diff(workspace),
    )

    return reg
