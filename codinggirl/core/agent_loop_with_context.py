"""
Agent Loop with Context Management - 集成上下文管理的增强版

扩展 AgentLoopWithTodo，添加 Context Management 支持：
1. Micro-compact: 每轮自动压缩旧工具结果
2. Auto-compact: Token 超过阈值时自动生成摘要
3. Context stats 追踪和事件记录
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field

from codinggirl.core.context_manager import ContextManager
from codinggirl.core.contracts import Plan, ToolCall as ContractToolCall
from codinggirl.core.contracts import ToolResult, utc_now_iso
from codinggirl.core.policy import PermissionPolicy
from codinggirl.core.todo_manager import TodoManager
from codinggirl.core.todo_tool import create_todo_handler, create_todo_tool_spec
from codinggirl.runtime.llm_adapter.base import LLMProvider
from codinggirl.runtime.llm_adapter.models import ChatMessage, ToolSchema
from codinggirl.runtime.storage_sqlite import SQLiteStore
from codinggirl.runtime.tools.registry import ToolRegistry
from codinggirl.runtime.tools.runner import ToolRunner


@dataclass
class AgentLoopWithContextConfig:
    """Agent Loop 配置（带 Context Management）"""

    max_iterations: int = 50
    temperature: float = 0.0
    system_prompt: str | None = None
    enable_todo: bool = True
    enable_context_management: bool = True
    keep_recent_results: int = 3  # Micro-compact 保留数量
    token_threshold: int = 50000  # Auto-compact 阈值
    nag_threshold: int = 3


@dataclass
class AgentLoopWithContextResult:
    """Agent Loop 执行结果"""

    run_id: str
    success: bool
    final_message: str
    iterations: int
    todo_stats: dict[str, int] | None = None
    context_stats: dict[str, int] | None = None
    error: str | None = None


@dataclass
class AgentLoopWithContext:
    """
    Agent Loop with Context Management

    在 AgentLoopWithTodo 基础上添加上下文管理能力
    """

    llm: LLMProvider
    registry: ToolRegistry
    store: SQLiteStore
    repo_root: str
    config: AgentLoopWithContextConfig = field(default_factory=AgentLoopWithContextConfig)

    def run(
        self,
        *,
        user_goal: str,
        permission_mode: str = "write",
        run_id: str | None = None,
        initial_plan: Plan | None = None,
    ) -> AgentLoopWithContextResult:
        """执行 agent loop（带 context management）"""
        if run_id is None:
            run_id = uuid.uuid4().hex

        # 初始化 run
        self.store.create_run(
            run_id,
            created_at=utc_now_iso(),
            metadata={"goal": user_goal, "repo_root": self.repo_root},
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

        # 初始化 ContextManager
        context_manager: ContextManager | None = None
        if self.config.enable_context_management:
            context_manager = ContextManager(
                keep_recent_results=self.config.keep_recent_results,
                token_threshold=self.config.token_threshold,
            )

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

        # 如果有 todo_manager，临时注册 todo 工具
        if todo_manager:
            spec = create_todo_tool_spec()
            handler = create_todo_handler(todo_manager)
            self.registry.register(spec, handler)

        # 主循环
        iterations = 0
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

                # Context Management: Micro-compact
                if context_manager and iterations > 1:
                    messages, compact_stats = context_manager.micro_compact(messages)
                    if compact_stats["compacted"]:
                        self.store.append_event(
                            run_id=run_id,
                            kind="context_micro_compact",
                            ts=utc_now_iso(),
                            payload={
                                "iteration": iterations,
                                **compact_stats,
                            },
                        )

                # Context Management: Auto-compact check
                if context_manager and context_manager.should_auto_compact(messages):
                    messages, compact_stats = context_manager.auto_compact(messages, self.llm, run_id)
                    if compact_stats["compacted"]:
                        self.store.append_event(
                            run_id=run_id,
                            kind="context_auto_compact",
                            ts=utc_now_iso(),
                            payload={
                                "iteration": iterations,
                                **compact_stats,
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
                try:
                    response = self.llm.chat(
                        messages=messages,
                        tools=tool_schemas,
                        temperature=self.config.temperature,
                    )
                except Exception as e:
                    return AgentLoopWithContextResult(
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
                        "content": response.content,
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
                    # 没有工具调用，循环结束
                    self.store.append_event(
                        run_id=run_id,
                        kind="loop_complete",
                        ts=utc_now_iso(),
                        payload={"iterations": iterations, "reason": "no_tool_calls"},
                    )

                    # 获取最终统计
                    final_context_stats = None
                    if context_manager:
                        stats = context_manager.get_stats(messages)
                        final_context_stats = {
                            "message_count": stats.message_count,
                            "token_count": stats.token_count,
                            "tool_result_count": stats.tool_result_count,
                            "compact_count": stats.compact_count,
                        }

                    return AgentLoopWithContextResult(
                        run_id=run_id,
                        success=True,
                        final_message=response.content,
                        iterations=iterations,
                        todo_stats=todo_manager.get_stats() if todo_manager else None,
                        context_stats=final_context_stats,
                    )

                # 执行工具调用
                for tc in response.tool_calls:
                    try:
                        args = json.loads(tc.arguments_json)
                    except json.JSONDecodeError as e:
                        args = {}
                        error_msg = f"Invalid JSON in tool arguments: {e}"
                        self.store.append_event(
                            run_id=run_id,
                            kind="tool_parse_error",
                            ts=utc_now_iso(),
                            payload={"tool_call_id": tc.id, "error": error_msg},
                        )

                    result = runner.call(tc.name, args, call_id=tc.id)

                    if tc.name == "todo_update" and result.ok and todo_manager:
                        todo_manager.mark_updated(iterations)
                        self.store.append_event(
                            run_id=run_id,
                            kind="todo_updated",
                            ts=utc_now_iso(),
                            payload={"stats": todo_manager.get_stats()},
                        )

                    result_content = self._format_tool_result(result)
                    messages.append(
                        ChatMessage(
                            role="tool",
                            content=result_content,
                            tool_call_id=tc.id,
                        )
                    )

            # 达到最大迭代次数
            self.store.append_event(
                run_id=run_id,
                kind="loop_max_iterations",
                ts=utc_now_iso(),
                payload={"iterations": iterations},
            )
            return AgentLoopWithContextResult(
                run_id=run_id,
                success=False,
                final_message="",
                iterations=iterations,
                error=f"Reached max iterations ({self.config.max_iterations})",
            )

        except Exception as e:
            self.store.append_event(
                run_id=run_id,
                kind="loop_error",
                ts=utc_now_iso(),
                payload={"error": str(e), "iterations": iterations},
            )
            return AgentLoopWithContextResult(
                run_id=run_id,
                success=False,
                final_message="",
                iterations=iterations,
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
