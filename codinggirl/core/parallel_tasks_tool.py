"""
并行任务工具 - 让主 agent 可以并行执行多个子任务

提供 parallel_tasks 工具，支持：
1. 手动指定多个并行任务
2. 自动分解复杂任务
3. 结果自动综合
"""
from __future__ import annotations

from typing import Any

from codinggirl.core.contracts import ToolResult
from codinggirl.core.parallel_agent_orchestrator import (
    ParallelAgentOrchestrator,
    ParallelTask,
)
from codinggirl.runtime.tools.spec import ToolSpec


def create_parallel_tasks_tool_spec() -> ToolSpec:
    """创建 parallel_tasks 工具规范"""
    return ToolSpec(
        name="parallel_tasks",
        description="""Execute multiple independent tasks in parallel using subagents.

Use this when you need to:
- Explore multiple directories simultaneously
- Analyze different aspects of the codebase in parallel
- Gather information from multiple sources concurrently

This is much faster than executing tasks sequentially.

Examples:
1. Explore multiple directories:
   parallel_tasks(tasks=[
     {"description": "Analyze frontend code", "context": "Focus on src/renderer/"},
     {"description": "Analyze backend code", "context": "Focus on python-server/"}
   ])

2. Multi-aspect analysis:
   parallel_tasks(tasks=[
     {"description": "Find all API endpoints"},
     {"description": "Find all database queries"},
     {"description": "Find all error handling"}
   ])

3. Auto-decompose complex task:
   parallel_tasks(
     auto_decompose=true,
     complex_task="Analyze the entire codebase for security issues"
   )
""",
        input_schema={
            "type": "object",
            "properties": {
                "tasks": {
                    "type": "array",
                    "description": "List of parallel tasks to execute",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "Task description (what to do)",
                            },
                            "context": {
                                "type": "string",
                                "description": "Additional context for the task",
                            },
                            "priority": {
                                "type": "integer",
                                "description": "Priority (higher = execute first)",
                                "default": 0,
                            },
                        },
                        "required": ["description"],
                    },
                },
                "auto_decompose": {
                    "type": "boolean",
                    "description": "Automatically decompose a complex task into parallel subtasks",
                    "default": False,
                },
                "complex_task": {
                    "type": "string",
                    "description": "Complex task to auto-decompose (only if auto_decompose=true)",
                },
                "synthesize_results": {
                    "type": "boolean",
                    "description": "Synthesize results into a unified summary",
                    "default": True,
                },
            },
            "oneOf": [
                {"required": ["tasks"]},
                {"required": ["auto_decompose", "complex_task"]},
            ],
        },
        required_permission="readonly",  # 子任务默认只读
        risk_level="low",
    )


def create_parallel_tasks_handler(orchestrator: ParallelAgentOrchestrator):
    """创建 parallel_tasks 工具处理器"""

    def handler(
        tasks: list[dict[str, Any]] | None = None,
        auto_decompose: bool = False,
        complex_task: str | None = None,
        synthesize_results: bool = True,
    ) -> ToolResult:
        """执行并行任务"""
        try:
            # 模式 1: 手动指定任务
            if tasks:
                parallel_tasks = []
                for i, task_dict in enumerate(tasks):
                    parallel_tasks.append(
                        ParallelTask(
                            task_id=f"task_{i}",
                            description=task_dict.get("description", ""),
                            context=task_dict.get("context", ""),
                            priority=task_dict.get("priority", 0),
                        )
                    )

            # 模式 2: 自动分解
            elif auto_decompose and complex_task:
                parallel_tasks = orchestrator.decompose_task(complex_task)

            else:
                return ToolResult(
                    ok=False,
                    error="Must provide either 'tasks' or 'auto_decompose=true' with 'complex_task'",
                )

            # 执行并行任务
            results = orchestrator.execute_parallel(parallel_tasks)

            # 综合结果
            if synthesize_results:
                synthesized = orchestrator.synthesize_results(results)
                return ToolResult(
                    ok=True,
                    content={
                        "summary": synthesized,
                        "task_count": len(results),
                        "success_count": sum(1 for r in results if r.success),
                        "total_time_sec": sum(r.execution_time_sec for r in results),
                        "details": [
                            {
                                "task_id": r.task_id,
                                "success": r.success,
                                "execution_time_sec": r.execution_time_sec,
                                "error": r.error,
                            }
                            for r in results
                        ],
                    },
                )
            else:
                # 不综合，返回原始结果
                return ToolResult(
                    ok=True,
                    content={
                        "results": [
                            {
                                "task_id": r.task_id,
                                "success": r.success,
                                "result": r.result if r.success else None,
                                "error": r.error,
                                "execution_time_sec": r.execution_time_sec,
                            }
                            for r in results
                        ],
                        "task_count": len(results),
                        "success_count": sum(1 for r in results if r.success),
                    },
                )

        except Exception as e:
            return ToolResult(
                ok=False,
                error=f"Parallel tasks execution failed: {e}",
            )

    return handler
