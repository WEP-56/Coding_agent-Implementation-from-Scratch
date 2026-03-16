"""
并行 Agent 系统 - 真正的多 agent 并行执行

核心特性：
1. 多个 subagent 真正并行执行（ThreadPoolExecutor）
2. 智能任务分解和分配
3. 结果汇总和冲突解决
4. 进度实时追踪
5. 失败重试和降级策略
"""
from __future__ import annotations

import concurrent.futures
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from codinggirl.core.contracts import ToolResult, utc_now_iso
from codinggirl.core.subagent_runner import SubagentConfig, SubagentRunner
from codinggirl.runtime.llm_adapter.base import LLMProvider
from codinggirl.runtime.storage_sqlite import SQLiteStore
from codinggirl.runtime.tools.registry import ToolRegistry


@dataclass
class ParallelTask:
    """并行任务定义"""

    task_id: str
    description: str
    context: str
    priority: int = 0  # 优先级（高优先级先执行）
    timeout_sec: float = 300.0  # 超时时间
    retry_on_failure: bool = True  # 失败是否重试
    dependencies: list[str] = field(default_factory=list)  # 依赖的任务 ID


@dataclass
class ParallelTaskResult:
    """并行任务结果"""

    task_id: str
    success: bool
    result: str
    execution_time_sec: float
    error: str | None = None
    retry_count: int = 0


@dataclass
class ParallelAgentConfig:
    """并行 Agent 配置"""

    max_parallel_agents: int = 4  # 最大并行数
    enable_auto_decomposition: bool = True  # 自动任务分解
    enable_result_synthesis: bool = True  # 结果综合
    subagent_config: SubagentConfig = field(default_factory=SubagentConfig)


class ParallelAgentOrchestrator:
    """
    并行 Agent 编排器

    负责：
    1. 任务分解（可选）
    2. 并行执行多个 subagent
    3. 结果汇总
    4. 进度追踪
    """

    def __init__(
        self,
        llm: LLMProvider,
        registry: ToolRegistry,
        store: SQLiteStore,
        parent_run_id: str,
        config: ParallelAgentConfig | None = None,
    ):
        self.llm = llm
        self.registry = registry
        self.store = store
        self.parent_run_id = parent_run_id
        self.config = config or ParallelAgentConfig()

        # 任务状态追踪
        self.task_results: dict[str, ParallelTaskResult] = {}
        self.task_progress: dict[str, float] = {}  # task_id -> progress (0-1)

    def execute_parallel(
        self,
        tasks: list[ParallelTask],
        on_progress: Callable[[str, float], None] | None = None,
    ) -> list[ParallelTaskResult]:
        """
        并行执行多个任务

        Args:
            tasks: 任务列表
            on_progress: 进度回调函数 (task_id, progress)

        Returns:
            任务结果列表（按原顺序）
        """
        start_time = time.time()

        # 记录开始事件
        self.store.append_event(
            run_id=self.parent_run_id,
            kind="parallel_agents_start",
            ts=utc_now_iso(),
            payload={
                "task_count": len(tasks),
                "max_parallel": self.config.max_parallel_agents,
                "tasks": [
                    {
                        "task_id": t.task_id,
                        "description": t.description,
                        "priority": t.priority,
                    }
                    for t in tasks
                ],
            },
        )

        # 按依赖关系排序任务
        sorted_tasks = self._topological_sort(tasks)

        # 并行执行
        results = self._execute_with_dependencies(sorted_tasks, on_progress)

        # 记录完成事件
        total_time = time.time() - start_time
        success_count = sum(1 for r in results if r.success)

        self.store.append_event(
            run_id=self.parent_run_id,
            kind="parallel_agents_complete",
            ts=utc_now_iso(),
            payload={
                "task_count": len(tasks),
                "success_count": success_count,
                "failed_count": len(tasks) - success_count,
                "total_time_sec": total_time,
                "avg_time_sec": total_time / len(tasks) if tasks else 0,
            },
        )

        return results

    def decompose_task(self, complex_task: str, context: str = "") -> list[ParallelTask]:
        """
        自动分解复杂任务为多个并行子任务

        使用 LLM 分析任务并生成分解方案
        """
        if not self.config.enable_auto_decomposition:
            # 不分解，返回单个任务
            return [
                ParallelTask(
                    task_id=uuid.uuid4().hex[:8],
                    description=complex_task,
                    context=context,
                )
            ]

        # 调用 LLM 分解任务
        decomposition_prompt = f"""Analyze this task and decompose it into 2-5 independent parallel subtasks.

Task: {complex_task}
Context: {context}

Requirements:
1. Each subtask should be independent (can run in parallel)
2. Each subtask should be focused and specific
3. Subtasks should cover the entire original task
4. Return JSON format

Example output:
{{
  "subtasks": [
    {{
      "description": "Analyze frontend code structure",
      "context": "Focus on src/renderer/ directory",
      "priority": 1
    }},
    {{
      "description": "Analyze backend API endpoints",
      "context": "Focus on python-server/ directory",
      "priority": 1
    }}
  ]
}}

Return ONLY the JSON, no explanation."""

        try:
            from codinggirl.runtime.llm_adapter.models import ChatMessage

            response = self.llm.chat(
                messages=[ChatMessage(role="user", content=decomposition_prompt)],
                temperature=0.0,
            )

            # 解析 JSON
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]

            data = json.loads(content.strip())
            subtasks = data.get("subtasks", [])

            if not subtasks:
                # 分解失败，返回原任务
                return [
                    ParallelTask(
                        task_id=uuid.uuid4().hex[:8],
                        description=complex_task,
                        context=context,
                    )
                ]

            # 转换为 ParallelTask
            tasks = []
            for i, st in enumerate(subtasks):
                tasks.append(
                    ParallelTask(
                        task_id=f"auto_{i}_{uuid.uuid4().hex[:6]}",
                        description=st.get("description", ""),
                        context=st.get("context", ""),
                        priority=st.get("priority", 0),
                    )
                )

            self.store.append_event(
                run_id=self.parent_run_id,
                kind="task_decomposed",
                ts=utc_now_iso(),
                payload={
                    "original_task": complex_task,
                    "subtask_count": len(tasks),
                    "subtasks": [t.description for t in tasks],
                },
            )

            return tasks

        except Exception as e:
            # 分解失败，返回原任务
            self.store.append_event(
                run_id=self.parent_run_id,
                kind="task_decomposition_failed",
                ts=utc_now_iso(),
                payload={"error": str(e)},
            )

            return [
                ParallelTask(
                    task_id=uuid.uuid4().hex[:8],
                    description=complex_task,
                    context=context,
                )
            ]

    def synthesize_results(self, results: list[ParallelTaskResult]) -> str:
        """
        综合多个子任务的结果

        使用 LLM 将多个结果合并为一个连贯的总结
        """
        if not self.config.enable_result_synthesis:
            # 不综合，简单拼接
            parts = []
            for r in results:
                if r.success:
                    parts.append(f"## {r.task_id}\n\n{r.result}")
                else:
                    parts.append(f"## {r.task_id}\n\n❌ Failed: {r.error}")
            return "\n\n".join(parts)

        # 调用 LLM 综合结果
        synthesis_prompt = f"""Synthesize the following parallel task results into a coherent summary.

Task Results:
"""
        for i, r in enumerate(results, 1):
            if r.success:
                synthesis_prompt += f"\n### Task {i}: {r.task_id}\n{r.result}\n"
            else:
                synthesis_prompt += f"\n### Task {i}: {r.task_id}\n❌ Failed: {r.error}\n"

        synthesis_prompt += """
Requirements:
1. Create a unified, coherent summary
2. Highlight key findings from each task
3. Identify patterns and connections
4. Note any conflicts or inconsistencies
5. Keep it concise but comprehensive

Return the synthesized summary:"""

        try:
            from codinggirl.runtime.llm_adapter.models import ChatMessage

            response = self.llm.chat(
                messages=[ChatMessage(role="user", content=synthesis_prompt)],
                temperature=0.0,
            )

            return response.content

        except Exception as e:
            # 综合失败，返回简单拼接
            self.store.append_event(
                run_id=self.parent_run_id,
                kind="result_synthesis_failed",
                ts=utc_now_iso(),
                payload={"error": str(e)},
            )

            parts = []
            for r in results:
                if r.success:
                    parts.append(f"## {r.task_id}\n\n{r.result}")
            return "\n\n".join(parts)

    def _execute_with_dependencies(
        self,
        tasks: list[ParallelTask],
        on_progress: Callable[[str, float], None] | None = None,
    ) -> list[ParallelTaskResult]:
        """
        考虑依赖关系的并行执行

        按拓扑排序执行，同一层级的任务并行
        """
        # 构建依赖图
        task_map = {t.task_id: t for t in tasks}
        completed = set()
        results_map: dict[str, ParallelTaskResult] = {}

        # 按层级执行
        while len(completed) < len(tasks):
            # 找出可以执行的任务（依赖已完成）
            ready_tasks = [
                t
                for t in tasks
                if t.task_id not in completed and all(dep in completed for dep in t.dependencies)
            ]

            if not ready_tasks:
                # 没有可执行的任务，可能有循环依赖
                remaining = [t for t in tasks if t.task_id not in completed]
                for t in remaining:
                    results_map[t.task_id] = ParallelTaskResult(
                        task_id=t.task_id,
                        success=False,
                        result="",
                        execution_time_sec=0,
                        error="Circular dependency or unmet dependencies",
                    )
                    completed.add(t.task_id)
                break

            # 并行执行这一批任务
            batch_results = self._execute_batch(ready_tasks, on_progress)

            for result in batch_results:
                results_map[result.task_id] = result
                completed.add(result.task_id)

        # 按原顺序返回结果
        return [results_map[t.task_id] for t in tasks]

    def _execute_batch(
        self,
        tasks: list[ParallelTask],
        on_progress: Callable[[str, float], None] | None = None,
    ) -> list[ParallelTaskResult]:
        """并行执行一批任务"""
        results: list[ParallelTaskResult] = []

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(len(tasks), self.config.max_parallel_agents)
        ) as executor:
            # 提交所有任务
            future_to_task = {
                executor.submit(self._execute_single_task, task, on_progress): task for task in tasks
            }

            # 等待完成
            for future in concurrent.futures.as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    # 执行失败
                    results.append(
                        ParallelTaskResult(
                            task_id=task.task_id,
                            success=False,
                            result="",
                            execution_time_sec=0,
                            error=f"Execution exception: {e}",
                        )
                    )

        return results

    def _execute_single_task(
        self,
        task: ParallelTask,
        on_progress: Callable[[str, float], None] | None = None,
    ) -> ParallelTaskResult:
        """执行单个任务（在线程中）"""
        start_time = time.time()
        retry_count = 0

        # 记录任务开始
        self.store.append_event(
            run_id=self.parent_run_id,
            kind="parallel_task_start",
            ts=utc_now_iso(),
            payload={
                "task_id": task.task_id,
                "description": task.description,
            },
        )

        while retry_count <= (1 if task.retry_on_failure else 0):
            try:
                # 创建 subagent runner
                runner = SubagentRunner(
                    llm=self.llm,
                    registry=self.registry,
                    store=self.store,
                    parent_run_id=self.parent_run_id,
                    config=self.config.subagent_config,
                )

                # 执行任务
                result = runner.run(task=task.description, context=task.context)

                execution_time = time.time() - start_time

                # 记录任务完成
                self.store.append_event(
                    run_id=self.parent_run_id,
                    kind="parallel_task_complete",
                    ts=utc_now_iso(),
                    payload={
                        "task_id": task.task_id,
                        "success": result.ok,
                        "execution_time_sec": execution_time,
                        "retry_count": retry_count,
                    },
                )

                if on_progress:
                    on_progress(task.task_id, 1.0)

                if result.ok:
                    return ParallelTaskResult(
                        task_id=task.task_id,
                        success=True,
                        result=str(result.content),
                        execution_time_sec=execution_time,
                        retry_count=retry_count,
                    )
                else:
                    # 失败，可能重试
                    if retry_count < 1 and task.retry_on_failure:
                        retry_count += 1
                        continue
                    else:
                        return ParallelTaskResult(
                            task_id=task.task_id,
                            success=False,
                            result="",
                            execution_time_sec=execution_time,
                            error=result.error,
                            retry_count=retry_count,
                        )

            except Exception as e:
                execution_time = time.time() - start_time

                # 记录任务失败
                self.store.append_event(
                    run_id=self.parent_run_id,
                    kind="parallel_task_error",
                    ts=utc_now_iso(),
                    payload={
                        "task_id": task.task_id,
                        "error": str(e),
                        "retry_count": retry_count,
                    },
                )

                if retry_count < 1 and task.retry_on_failure:
                    retry_count += 1
                    continue
                else:
                    return ParallelTaskResult(
                        task_id=task.task_id,
                        success=False,
                        result="",
                        execution_time_sec=execution_time,
                        error=str(e),
                        retry_count=retry_count,
                    )

        # 不应该到这里
        return ParallelTaskResult(
            task_id=task.task_id,
            success=False,
            result="",
            execution_time_sec=time.time() - start_time,
            error="Unknown error",
        )

    def _topological_sort(self, tasks: list[ParallelTask]) -> list[ParallelTask]:
        """拓扑排序（处理依赖关系）"""
        # 简单实现：按优先级和依赖关系排序
        task_map = {t.task_id: t for t in tasks}
        sorted_tasks = []
        visited = set()

        def visit(task_id: str):
            if task_id in visited:
                return
            visited.add(task_id)

            task = task_map.get(task_id)
            if not task:
                return

            # 先访问依赖
            for dep in task.dependencies:
                visit(dep)

            sorted_tasks.append(task)

        # 访问所有任务
        for task in sorted(tasks, key=lambda t: -t.priority):
            visit(task.task_id)

        return sorted_tasks
