"""
Task Tool - 任务委托工具

允许父 agent 委托探索性任务给子 agent
"""
from __future__ import annotations

from typing import Any

from codinggirl.core.subagent_runner import SubagentRunner
from codinggirl.runtime.tools.registry import ToolSpec


def create_task_tool_spec() -> ToolSpec:
    """创建 task 工具规范"""
    return ToolSpec(
        name="task",
        description=(
            "Delegate an exploratory or research task to a subagent. "
            "Use this when you need to gather information from multiple files "
            "or explore the codebase without cluttering your context. "
            "The subagent will work independently and return a summary. "
            "\n\n"
            "Good use cases:\n"
            "- 'Find all API endpoints in this project'\n"
            "- 'What testing framework is used here?'\n"
            "- 'List all database models and their fields'\n"
            "- 'Search for all usages of function X'\n"
            "\n"
            "Bad use cases:\n"
            "- Tasks that require writing/modifying files\n"
            "- Tasks that need your current context\n"
            "- Simple single-file reads (just use fs_read_file)"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Clear description of what the subagent should do",
                },
                "context": {
                    "type": "string",
                    "description": "Optional context to help the subagent (e.g., relevant file paths, constraints)",
                },
            },
            "required": ["task"],
        },
        risk_level="low",
        required_permission=None,
    )


def create_task_handler(subagent_runner: SubagentRunner) -> callable:
    """
    创建 task 工具处理器

    Args:
        subagent_runner: SubagentRunner 实例
    """

    def handler(task: str, context: str | None = None) -> dict[str, Any]:
        """委托任务给子 agent"""
        result = subagent_runner.run(task_description=task, context=context)

        if result.success:
            return {
                "ok": True,
                "summary": result.summary,
                "stats": {
                    "iterations": result.iterations,
                    "tool_calls": result.tool_calls_count,
                },
            }
        else:
            return {
                "ok": False,
                "error": result.error or "Subagent task failed",
                "partial_summary": result.summary if result.summary else None,
                "stats": {
                    "iterations": result.iterations,
                    "tool_calls": result.tool_calls_count,
                },
            }

    return handler
