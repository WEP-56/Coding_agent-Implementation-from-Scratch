"""
Todo 工具 - 让 agent 更新任务进度

注册为标准工具，agent 可以调用来更新 todo 列表
"""
from __future__ import annotations

from codinggirl.core.contracts import ToolCall, ToolResult
from codinggirl.core.todo_manager import TodoManager
from codinggirl.runtime.tools.registry import ToolSpec


def create_todo_tool_spec() -> ToolSpec:
    """创建 todo 工具的 spec"""
    return ToolSpec(
        name="todo_update",
        description="Update task progress. Call this to mark tasks as in_progress or completed.",
        input_schema={
            "type": "object",
            "properties": {
                "updates": {
                    "type": "array",
                    "description": "List of task updates",
                    "items": {
                        "type": "object",
                        "properties": {
                            "step_id": {
                                "type": "string",
                                "description": "Task step ID (e.g., 's1', 's2')",
                            },
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed"],
                                "description": "New status for this task",
                            },
                        },
                        "required": ["step_id", "status"],
                    },
                }
            },
            "required": ["updates"],
        },
        risk_level="low",
        required_permission="read",
    )


def create_todo_handler(manager: TodoManager) -> callable:
    """创建 todo 工具的 handler（闭包捕获 manager）"""

    def handler(call: ToolCall) -> ToolResult:
        updates = call.args.get("updates", [])

        if not isinstance(updates, list):
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                ok=False,
                error="updates must be a list",
            )

        try:
            manager.update_from_list(updates)
            stats = manager.get_stats()

            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                ok=True,
                content={
                    "message": "Todo list updated successfully",
                    "stats": stats,
                    "current_progress": manager.render_for_prompt(),
                },
            )
        except Exception as e:
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                ok=False,
                error=f"Failed to update todo list: {e}",
            )

    return handler
