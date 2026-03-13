"""
Task Graph Tools - 任务图管理工具

允许 agent 创建、更新和查询任务依赖关系
"""
from __future__ import annotations

from typing import Any

from codinggirl.core.task_graph import TaskGraph
from codinggirl.runtime.tools.registry import ToolSpec


def create_task_create_tool_spec() -> ToolSpec:
    """创建 task_create 工具规范"""
    return ToolSpec(
        name="task_create",
        description=(
            "Create a new task in the task graph with optional dependencies.\n\n"
            "Use this to break down complex work into manageable tasks with clear dependencies. "
            "Tasks can depend on other tasks (blocked_by), and the system will automatically "
            "track when tasks become ready to execute.\n\n"
            "Example workflow:\n"
            "1. task_create(task_id='setup', title='Setup environment')\n"
            "2. task_create(task_id='build', title='Build project', blocked_by=['setup'])\n"
            "3. task_create(task_id='test', title='Run tests', blocked_by=['build'])\n\n"
            "The system ensures tasks are executed in the correct order."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "Unique task identifier (e.g., 'setup-env', 'run-tests')",
                },
                "title": {
                    "type": "string",
                    "description": "Short task title",
                },
                "description": {
                    "type": "string",
                    "description": "Detailed task description",
                },
                "blocked_by": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of task IDs that must complete before this task can start",
                },
            },
            "required": ["task_id", "title", "description"],
        },
        risk_level="low",
        required_permission=None,
    )


def create_task_update_tool_spec() -> ToolSpec:
    """创建 task_update 工具规范"""
    return ToolSpec(
        name="task_update",
        description=(
            "Update the status of a task in the task graph.\n\n"
            "Status values:\n"
            "- pending: Task not started yet\n"
            "- in_progress: Currently working on this task\n"
            "- completed: Task finished successfully\n"
            "- failed: Task failed\n"
            "- cancelled: Task cancelled\n\n"
            "When a task is marked as 'completed', any tasks that depend on it "
            "will be automatically unblocked."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "Task ID to update",
                },
                "status": {
                    "type": "string",
                    "enum": ["pending", "in_progress", "completed", "failed", "cancelled"],
                    "description": "New task status",
                },
            },
            "required": ["task_id", "status"],
        },
        risk_level="low",
        required_permission=None,
    )


def create_task_list_ready_tool_spec() -> ToolSpec:
    """创建 task_list_ready 工具规范"""
    return ToolSpec(
        name="task_list_ready",
        description=(
            "List all tasks that are ready to be executed.\n\n"
            "A task is ready if:\n"
            "1. Status is 'pending'\n"
            "2. All dependencies (blocked_by) are completed\n\n"
            "Use this to find out what tasks you can work on next."
        ),
        input_schema={
            "type": "object",
            "properties": {},
        },
        risk_level="low",
        required_permission=None,
    )


def create_task_list_tool_spec() -> ToolSpec:
    """创建 task_list 工具规范"""
    return ToolSpec(
        name="task_list",
        description=(
            "List all tasks in the task graph, optionally filtered by status.\n\n"
            "Returns task details including dependencies and current status."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["pending", "in_progress", "completed", "failed", "cancelled"],
                    "description": "Filter by status (optional)",
                }
            },
        },
        risk_level="low",
        required_permission=None,
    )


def create_task_get_tool_spec() -> ToolSpec:
    """创建 task_get 工具规范"""
    return ToolSpec(
        name="task_get",
        description="Get detailed information about a specific task, including its dependencies and status.",
        input_schema={
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "Task ID to retrieve",
                }
            },
            "required": ["task_id"],
        },
        risk_level="low",
        required_permission=None,
    )


def create_task_create_handler(task_graph: TaskGraph) -> callable:
    """创建 task_create 工具处理器"""

    def handler(
        task_id: str,
        title: str,
        description: str,
        blocked_by: list[str] | None = None,
    ) -> dict[str, Any]:
        """创建任务"""
        try:
            task = task_graph.create_task(
                task_id=task_id,
                title=title,
                description=description,
                blocked_by=blocked_by,
            )

            return {
                "ok": True,
                "task_id": task.task_id,
                "title": task.title,
                "status": task.status,
                "blocked_by": task.blocked_by,
                "message": f"Task created: {task_id}",
            }
        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
            }

    return handler


def create_task_update_handler(task_graph: TaskGraph) -> callable:
    """创建 task_update 工具处理器"""

    def handler(task_id: str, status: str) -> dict[str, Any]:
        """更新任务状态"""
        try:
            task = task_graph.update_task_status(task_id, status)  # type: ignore[arg-type]

            result: dict[str, Any] = {
                "ok": True,
                "task_id": task.task_id,
                "status": task.status,
                "message": f"Task updated: {task_id} -> {status}",
            }

            # 如果任务完成，列出被解锁的任务
            if status == "completed":
                unblocked = []
                for blocked_id in task.blocks:
                    blocked_task = task_graph.get_task(blocked_id)
                    if blocked_task and not blocked_task.blocked_by:
                        unblocked.append(blocked_id)

                if unblocked:
                    result["unblocked_tasks"] = unblocked
                    result["message"] += f". Unblocked tasks: {', '.join(unblocked)}"

            return result
        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
            }

    return handler


def create_task_list_ready_handler(task_graph: TaskGraph) -> callable:
    """创建 task_list_ready 工具处理器"""

    def handler() -> dict[str, Any]:
        """列出可执行的任务"""
        ready_tasks = task_graph.list_ready_tasks()

        tasks_info = [
            {
                "task_id": t.task_id,
                "title": t.title,
                "description": t.description,
            }
            for t in ready_tasks
        ]

        return {
            "ok": True,
            "ready_tasks": tasks_info,
            "count": len(ready_tasks),
        }

    return handler


def create_task_list_handler(task_graph: TaskGraph) -> callable:
    """创建 task_list 工具处理器"""

    def handler(status: str | None = None) -> dict[str, Any]:
        """列出所有任务"""
        tasks = task_graph.list_tasks(status=status)  # type: ignore[arg-type]

        tasks_info = [
            {
                "task_id": t.task_id,
                "title": t.title,
                "description": t.description,
                "status": t.status,
                "blocked_by": t.blocked_by,
                "blocks": t.blocks,
            }
            for t in tasks
        ]

        stats = task_graph.get_stats()

        return {
            "ok": True,
            "tasks": tasks_info,
            "stats": stats,
        }

    return handler


def create_task_get_handler(task_graph: TaskGraph) -> callable:
    """创建 task_get 工具处理器"""

    def handler(task_id: str) -> dict[str, Any]:
        """获取任务详情"""
        task = task_graph.get_task(task_id)

        if not task:
            return {
                "ok": False,
                "error": f"Task not found: {task_id}",
            }

        return {
            "ok": True,
            "task": {
                "task_id": task.task_id,
                "title": task.title,
                "description": task.description,
                "status": task.status,
                "blocked_by": task.blocked_by,
                "blocks": task.blocks,
                "created_at": task.created_at,
                "started_at": task.started_at,
                "completed_at": task.completed_at,
                "metadata": task.metadata,
            },
        }

    return handler
