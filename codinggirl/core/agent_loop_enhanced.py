"""
Enhanced Agent Loop - 集成所有优化的增强版

集成优化：
1. Advanced Context Manager（智能压缩）
2. Loop Guards（循环守护）
3. Parallel Tool Runner（并行执行）
4. 改进的事件记录
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field

from codinggirl.core.advanced_context_manager import AdvancedContextManager, TaskPhase
from codinggirl.core.contracts import Plan, ToolCall as ContractToolCall
from codinggirl.core.contracts import ToolResult, utc_now_iso
from codinggirl.core.loop_guards import CircuitBreaker, LoopGuard
from codinggirl.core.policy import PermissionPolicy
from codinggirl.core.todo_manager import TodoManager
from codinggirl.core.todo_tool import create_todo_handler, create_todo_tool_spec
from codinggirl.runtime.llm_adapter.base import LLMProvider
from codinggirl.runtime.llm_adapter.models import ChatMessage, ToolSchema
from codinggirl.runtime.storage_sqlite import SQLiteStore
from codinggirl.runtime.tools.parallel_runner import ParallelToolRunner
from codinggirl.runtime.tools.registry import ToolRegistry
from codinggirl.runtime.tools.runner import ToolRunner


@dataclass
class EnhancedAgentLoopConfig:
    """增强版 Agent Loop 配置"""

    max_iterations: int = 50
    temperature: float = 0.0
    system_prompt: str | None = None

    # Todo 配置
    enable_todo: bool = True
    nag_threshold: int = 3

    # Context 配置
    enable_context_management: bool = True
    context_window_size: int = 15  # 滑动窗口大小
    context_max_tokens: int = 100000  # 最大 token 数
    enable_prompt_caching: bool = False  # Prompt Caching（需要 API 支持）

    # Loop Guards 配置
    enable_loop_guards: bool = True
    max_consecutive_identical: int = 3
    max_failed_retry: int = 2

    # Parallel Execution 配置
    enable_parallel_execution: bool = True
    max_parallel_workers: int = 4


@dataclass
class EnhancedAgentLoopResult:
    """增强版 Agent Loop 执行结果"""

    run_id: str
    success: bool
    final_message: str
    iterations: int
    todo_stats: dict[str, int] | None = None
    context_stats: dict[str, object] | None = None
    loop_guard_stats: dict[str, object] | None = None
    performance_stats: dict[str, float] | None = None
    error: str | None = None


@dataclass
class EnhancedAgentLoop:
    """
    增强版 Agent Loop

    集成所有优化：
    - Advanced Context Manager（智能压缩）
    - Loop Guards（循环守护）
    - Parallel Tool Runner（并行执行）
    - 性能监控
    """

    llm: LLMProvider
    registry: ToolRegistry
    store: SQLiteStore
    repo_root: str
    config: EnhancedAgentLoopConfig = field(default_factory=EnhancedAgentLoopConfig)

    def run(
        self,
        *,
        user_goal: str,
        permission_mode: str = "write",
        run_id: str | None = None,
        initial_plan: Plan | None = None,
        task_phase: TaskPhase = "exploration",
    ) -> EnhancedAgentLoopResult:
        """执行增强版 agent loop"""
        if run_id is None:
            run_id = uuid.uuid4().hex

        # 性能统计
        start_time = time.time()
        llm_time = 0.0
        tool_time = 0.0

        # 初始化 run
        self.store.create_run(
            run_id,
            created_at=utc_now_iso(),
            metadata={
                "goal": user_goal,
                "repo_root": self.repo_root,
                "task_phase": task_phase,
            },
        )

        # 初始化 TodoManager
        todo_manager: TodoManager | None = None
        if self.config.enable_todo and initial_plan:
            todo_manager = TodoManager.from_plan(initial_plan)
            self.store.append_event(
                run_id=run_id,
                kind="todo_initialized",
                ts=utc_now_iso(),
                payload={"stats": todo_manager.get_stats()},
            )

        # 初始化 Advanced Context Manager
        context_manager: AdvancedContextManager | None = None
        if self.config.enable_context_management:
            context_manager = AdvancedContextManager(
                window_size=self.config.context_window_size,
                max_tokens=self.config.context_max_tokens,
                enable_prompt_caching=self.config.enable_prompt_caching,
            )

        # 初始化 Loop Guards
        loop_guard: LoopGuard | None = None
        circuit_breaker: CircuitBreaker | None = None
        if self.config.enable_loop_guards:
            loop_guard = LoopGuard(
                max_consecutive_identical=self.config.max_consecutive_identical,
                max_failed_retry=self.config.max_failed_retry,
            )
            circuit_breaker = CircuitBreaker()

        # 构建 system prompt
        system_prompt = self._build_system_prompt(todo_manager)

        # 初始化 message history
        messages: list[ChatMessage] = []
        if system_prompt:
            messages.append(ChatMessage(role="system", content=system_prompt))
        messages.append(ChatMessage(role="user", content=user_goal))

        # 准备工具 schemas
        tool_schemas = self._build_tool_schemas(todo_manager)

        # 创建 ToolRunner
        permission = PermissionPolicy(mode=permission_mode)  # type: ignore[arg-type]
        runner = ToolRunner(
            registry=self.registry,
            store=self.store,
            run_id=run_id,
            permission=permission,
        )

        # 创建 Parallel Tool Runner
        parallel_runner: ParallelToolRunner | None = None
        if self.config.enable_parallel_execution:
            parallel_runner = ParallelToolRunner(
                runner=runner,
                max_workers=self.config.max_parallel_workers,
            )

        # 如果有 todo_manager，临时注册 todo 工具
        if todo_manager:
            spec = create_todo_tool_spec()
            handler = create_todo_handler(todo_manager)
            self.registry.register(spec, handler)

        # 主循环
        iterations = 0
        last_tool_failed = False

        try:
            while iterations < self.config.max_iterations:
                iterations += 1

                # 记录当前轮次
                self.store.append_event(
                    run_id=run_id,
                    kind="loop_iteration",
                    ts=utc_now_iso(),
                    payload={"iteration": iterations, "message_count": len(messages)},
                )

                # 检查断路器
                if circuit_breaker:
                    can_proceed, reason = circuit_breaker.can_proceed()
                    if not can_proceed:
                        self.store.append_event(
                            run_id=run_id,
                            kind="circuit_breaker_open",
                            ts=utc_now_iso(),
                            payload={"reason": reason},
                        )
                        return EnhancedAgentLoopResult(
                            run_id=run_id,
                            success=False,
                            final_message="",
                            iterations=iterations,
                            error=reason,
                        )

                # Context Management: 检查是否需要压缩
                if context_manager:
                    should_compress, trigger_reason = context_manager.should_compress(
                        messages, iterations, task_phase
                    )

                    if should_compress:
                        compress_start = time.time()
                        messages, metrics = context_manager.compress(
                            messages, iterations, task_phase
                        )
                        compress_time = (time.time() - compress_start) * 1000

                        self.store.append_event(
                            run_id=run_id,
                            kind="context_compressed",
                            ts=utc_now_iso(),
                            payload={
                                "iteration": iterations,
                                "trigger_reason": trigger_reason,
                                "compression_ratio": metrics.compression_ratio,
                                "tokens_saved": metrics.tokens_saved,
                                "compression_time_ms": compress_time,
                            },
                        )

                # 检查是否需要 nag reminder
                if todo_manager and todo_manager.should_nag(iterations):
                    nag_message = (
                        "\n\n[REMINDER] Please update your task progress using the todo_update tool."
                    )
                    if messages and messages[-1].role == "user":
                        messages[-1] = ChatMessage(
                            role="user",
                            content=messages[-1].content + nag_message,
                        )

                # 调用 LLM
                llm_start = time.time()
                try:
                    response = self.llm.chat(
                        messages=messages,
                        tools=tool_schemas,
                        temperature=self.config.temperature,
                    )
                    llm_time += time.time() - llm_start

                    if circuit_breaker:
                        circuit_breaker.record_success()

                except Exception as e:
                    llm_time += time.time() - llm_start

                    if circuit_breaker:
                        circuit_breaker.record_failure()

                    self.store.append_event(
                        run_id=run_id,
                        kind="llm_error",
                        ts=utc_now_iso(),
                        payload={"error": str(e), "iteration": iterations},
                    )

                    return EnhancedAgentLoopResult(
                        run_id=run_id,
                        success=False,
                        final_message="",
                        iterations=iterations,
                        error=f"LLM call failed: {e}",
                    )

                # 记录 LLM 响应
                self.store.append_event(
                    run_id=run_id,
                    kind="llm_response",
                    ts=utc_now_iso(),
                    payload={
                        "content": response.content[:500],  # 截断
                        "finish_reason": response.finish_reason,
                        "tool_calls_count": len(response.tool_calls),
                    },
                )

                # 将 assistant 消息追加到 history
                messages.append(
                    ChatMessage(
                        role="assistant",
                        content=response.content,
                        tool_calls=response.tool_calls if response.tool_calls else None,
                    )
                )

                # 检查是否有 tool_calls
                if not response.tool_calls:
                    # 检查无进展情况
                    if loop_guard:
                        is_safe, warning = loop_guard.check_iteration(has_tool_calls=False)
                        if not is_safe:
                            self.store.append_event(
                                run_id=run_id,
                                kind="loop_guard_warning",
                                ts=utc_now_iso(),
                                payload={"warning": warning},
                            )
                            # 注入警告到 messages
                            messages.append(
                                ChatMessage(role="system", content=f"⚠️ {warning}")
                            )
                            continue  # 继续循环，让 agent 有机会恢复

                    # 没有工具调用，循环结束
                    self.store.append_event(
                        run_id=run_id,
                        kind="loop_complete",
                        ts=utc_now_iso(),
                        payload={"iterations": iterations, "reason": "no_tool_calls"},
                    )

                    return self._build_result(
                        run_id=run_id,
                        success=True,
                        final_message=response.content,
                        iterations=iterations,
                        todo_manager=todo_manager,
                        context_manager=context_manager,
                        loop_guard=loop_guard,
                        messages=messages,
                        start_time=start_time,
                        llm_time=llm_time,
                        tool_time=tool_time,
                    )

                # 执行工具调用
                tool_start = time.time()

                # 准备工具调用批次
                tool_calls_batch = []
                for tc in response.tool_calls:
                    try:
                        args = json.loads(tc.arguments_json)
                    except json.JSONDecodeError as e:
                        args = {}
                        self.store.append_event(
                            run_id=run_id,
                            kind="tool_parse_error",
                            ts=utc_now_iso(),
                            payload={"tool_call_id": tc.id, "error": str(e)},
                        )

                    # Loop Guard 检查
                    if loop_guard:
                        is_safe, warning = loop_guard.check_tool_call(
                            tc.name, args, last_tool_failed
                        )
                        if not is_safe:
                            self.store.append_event(
                                run_id=run_id,
                                kind="loop_guard_warning",
                                ts=utc_now_iso(),
                                payload={"tool": tc.name, "warning": warning},
                            )
                            # 注入警告
                            messages.append(
                                ChatMessage(
                                    role="tool",
                                    content=f"⚠️ {warning}",
                                    tool_call_id=tc.id,
                                )
                            )
                            last_tool_failed = True
                            continue

                    tool_calls_batch.append((tc.name, args, tc.id))

                # 执行工具调用（并行或串行）
                if parallel_runner and len(tool_calls_batch) > 1:
                    # 并行执行
                    self.store.append_event(
                        run_id=run_id,
                        kind="parallel_execution_start",
                        ts=utc_now_iso(),
                        payload={"tool_count": len(tool_calls_batch)},
                    )

                    results = parallel_runner.execute_batch(tool_calls_batch)

                    self.store.append_event(
                        run_id=run_id,
                        kind="parallel_execution_end",
                        ts=utc_now_iso(),
                        payload={"tool_count": len(tool_calls_batch)},
                    )
                else:
                    # 串行执行
                    results = [runner.call(name, args, call_id) for name, args, call_id in tool_calls_batch]

                tool_time += time.time() - tool_start

                # 处理结果
                last_tool_failed = False
                for i, (name, args, call_id) in enumerate(tool_calls_batch):
                    result = results[i]

                    if not result.ok:
                        last_tool_failed = True

                    # Todo 更新
                    if name == "todo_update" and result.ok and todo_manager:
                        todo_manager.mark_updated(iterations)
                        self.store.append_event(
                            run_id=run_id,
                            kind="todo_updated",
                            ts=utc_now_iso(),
                            payload={"stats": todo_manager.get_stats()},
                        )

                    # 追加结果到 messages
                    result_content = self._format_tool_result(result)
                    messages.append(
                        ChatMessage(
                            role="tool",
                            content=result_content,
                            tool_call_id=call_id,
                        )
                    )

            # 达到最大迭代次数
            self.store.append_event(
                run_id=run_id,
                kind="loop_max_iterations",
                ts=utc_now_iso(),
                payload={"iterations": iterations},
            )

            return self._build_result(
                run_id=run_id,
                success=False,
                final_message="",
                iterations=iterations,
                todo_manager=todo_manager,
                context_manager=context_manager,
                loop_guard=loop_guard,
                messages=messages,
                start_time=start_time,
                llm_time=llm_time,
                tool_time=tool_time,
                error=f"Reached max iterations ({self.config.max_iterations})",
            )

        except Exception as e:
            self.store.append_event(
                run_id=run_id,
                kind="loop_error",
                ts=utc_now_iso(),
                payload={"error": str(e), "iterations": iterations},
            )

            return self._build_result(
                run_id=run_id,
                success=False,
                final_message="",
                iterations=iterations,
                todo_manager=todo_manager,
                context_manager=context_manager,
                loop_guard=loop_guard,
                messages=messages,
                start_time=start_time,
                llm_time=llm_time,
                tool_time=tool_time,
                error=str(e),
            )

    def _build_system_prompt(self, todo_manager: TodoManager | None) -> str:
        """构建 system prompt"""
        base_prompt = self.config.system_prompt or ""

        if todo_manager:
            todo_section = "\n\n" + todo_manager.render_for_prompt()
            todo_section += "\n\nIMPORTANT: Use the todo_update tool to mark tasks as in_progress or completed."
            return base_prompt + todo_section

        return base_prompt

    def _build_tool_schemas(self, todo_manager: TodoManager | None) -> list[ToolSchema]:
        """构建工具 schemas"""
        schemas: list[ToolSchema] = []

        for spec in self.registry.list_specs():
            schemas.append(
                ToolSchema(
                    name=spec.name,
                    description=spec.description,
                    input_schema=spec.input_schema,
                )
            )

        if todo_manager:
            spec = create_todo_tool_spec()
            schemas.append(
                ToolSchema(
                    name=spec.name,
                    description=spec.description,
                    input_schema=spec.input_schema,
                )
            )

        return schemas

    def _format_tool_result(self, result: ToolResult) -> str:
        """格式化工具结果"""
        if not result.ok:
            return f"Error: {result.error}"

        parts: list[str] = []

        if result.content:
            if isinstance(result.content, dict):
                parts.append(json.dumps(result.content, ensure_ascii=False, indent=2))
            else:
                parts.append(str(result.content))

        if result.stdout:
            parts.append(f"stdout:\n{result.stdout}")

        if result.stderr:
            parts.append(f"stderr:\n{result.stderr}")

        return "\n\n".join(parts) if parts else "Success (no output)"

    def _build_result(
        self,
        *,
        run_id: str,
        success: bool,
        final_message: str,
        iterations: int,
        todo_manager: TodoManager | None,
        context_manager: AdvancedContextManager | None,
        loop_guard: LoopGuard | None,
        messages: list[ChatMessage],
        start_time: float,
        llm_time: float,
        tool_time: float,
        error: str | None = None,
    ) -> EnhancedAgentLoopResult:
        """构建结果对象"""
        # Todo 统计
        todo_stats = todo_manager.get_stats() if todo_manager else None

        # Context 统计
        context_stats = None
        if context_manager:
            stats = context_manager.get_stats()
            context_stats = {
                "compression_count": stats["compression_count"],
                "total_tokens_saved": stats["total_tokens_saved"],
                "avg_compression_ratio": stats["avg_compression_ratio"],
            }

        # Loop Guard 统计
        loop_guard_stats = loop_guard.get_stats() if loop_guard else None

        # 性能统计
        total_time = time.time() - start_time
        performance_stats = {
            "total_time_s": total_time,
            "llm_time_s": llm_time,
            "tool_time_s": tool_time,
            "avg_iteration_time_s": total_time / iterations if iterations > 0 else 0,
        }

        return EnhancedAgentLoopResult(
            run_id=run_id,
            success=success,
            final_message=final_message,
            iterations=iterations,
            todo_stats=todo_stats,
            context_stats=context_stats,
            loop_guard_stats=loop_guard_stats,
            performance_stats=performance_stats,
            error=error,
        )
