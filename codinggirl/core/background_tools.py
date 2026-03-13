"""
Background Task Tools - 后台任务工具

允许 agent 启动和检查后台任务
"""
from __future__ import annotations

from typing import Any

from codinggirl.core.background_manager import BackgroundManager
from codinggirl.runtime.tools.registry import ToolSpec


def create_run_background_tool_spec() -> ToolSpec:
    """创建 run_background 工具规范"""
    return ToolSpec(
        name="run_background",
        description=(
            "Run a shell command in the background without blocking. "
            "Use this for long-running commands like:\n"
            "- npm install / pip install (dependency installation)\n"
            "- npm run build / cargo build (compilation)\n"
            "- pytest / npm test (test suites)\n"
            "- npm run dev (development servers)\n\n"
            "The command will run asynchronously and you'll be notified when it completes. "
            "You can continue working on other tasks while it runs.\n\n"
            "Returns a task_id that you can use with check_background to get the result."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to run (e.g., 'npm install', 'pytest')",
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory (optional, defaults to repo root)",
                },
            },
            "required": ["command"],
        },
        risk_level="high",
        required_permission="exec",
    )


def create_check_background_tool_spec() -> ToolSpec:
    """创建 check_background 工具规范"""
    return ToolSpec(
        name="check_background",
        description=(
            "Check the status of a background task started with run_background.\n\n"
            "Returns:\n"
            "- status: pending, running, completed, failed, cancelled\n"
            "- exit_code: command exit code (if completed)\n"
            "- stdout: command output\n"
            "- stderr: command errors\n"
            "- duration: execution time in seconds"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "Task ID returned by run_background",
                }
            },
            "required": ["task_id"],
        },
        risk_level="low",
        required_permission=None,
    )


def create_list_background_tool_spec() -> ToolSpec:
    """创建 list_background 工具规范"""
    return ToolSpec(
        name="list_background",
        description=(
            "List all background tasks and their status.\n\n"
            "Useful for checking what tasks are currently running or completed."
        ),
        input_schema={
            "type": "object",
            "properties": {},
        },
        risk_level="low",
        required_permission=None,
    )


def create_run_background_handler(background_manager: BackgroundManager, repo_root: str) -> callable:
    """
    创建 run_background 工具处理器

    Args:
        background_manager: BackgroundManager 实例
        repo_root: 仓库根目录
    """

    def handler(command: str, cwd: str | None = None) -> dict[str, Any]:
        """启动后台任务"""
        # 如果没有指定 cwd，使用 repo_root
        if cwd is None:
            cwd = repo_root

        task_id = background_manager.start_task(command=command, cwd=cwd)

        return {
            "ok": True,
            "task_id": task_id,
            "command": command,
            "message": f"Background task started: {task_id}",
        }

    return handler


def create_check_background_handler(background_manager: BackgroundManager) -> callable:
    """
    创建 check_background 工具处理器

    Args:
        background_manager: BackgroundManager 实例
    """

    def handler(task_id: str) -> dict[str, Any]:
        """检查后台任务状态"""
        task = background_manager.get_task(task_id)

        if not task:
            return {
                "ok": False,
                "error": f"Task not found: {task_id}",
            }

        result: dict[str, Any] = {
            "ok": True,
            "task_id": task.task_id,
            "command": task.command,
            "status": task.status,
        }

        if task.exit_code is not None:
            result["exit_code"] = task.exit_code

        if task.stdout:
            result["stdout"] = task.stdout

        if task.stderr:
            result["stderr"] = task.stderr

        if task.start_time and task.end_time:
            result["duration"] = round(task.end_time - task.start_time, 2)

        if task.error:
            result["error"] = task.error

        return result

    return handler


def create_list_background_handler(background_manager: BackgroundManager) -> callable:
    """
    创建 list_background 工具处理器

    Args:
        background_manager: BackgroundManager 实例
    """

    def handler() -> dict[str, Any]:
        """列出所有后台任务"""
        tasks = background_manager.list_tasks()

        task_list = []
        for task in tasks:
            task_info = {
                "task_id": task.task_id,
                "command": task.command,
                "status": task.status,
            }

            if task.exit_code is not None:
                task_info["exit_code"] = task.exit_code

            if task.start_time and task.end_time:
                task_info["duration"] = round(task.end_time - task.start_time, 2)

            task_list.append(task_info)

        stats = background_manager.get_stats()

        return {
            "ok": True,
            "tasks": task_list,
            "stats": stats,
        }

    return handler
