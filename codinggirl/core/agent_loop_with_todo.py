"""
Agent Loop with TodoWrite - 集成任务追踪的增强版 Agent Loop

扩展 AgentLoop，添加 TodoManager 支持：
1. 自动生成初始 todo 列表
2. 注入到 system prompt
3. Nag reminder 机制
4. 注册 todo_update 工具
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field

from codinggirl.core.contracts import Plan, PlanStep, ToolCall as ContractToolCall
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
class AgentLoopWithTodoConfig:
    """Agent Loop 配置（带 Todo 支持）"""

    max_iterations: int = 50
    temperature: float = 0.0
    system_prompt: str | None = None
    enable_todo: bool = True  # 是否启用 todo 追踪
    nag_threshold: int = 3  # 多少轮未更新触发提醒


@dataclass
class AgentLoopWithTodoResult:
    """Agent Loop 执行结果"""

    run_id: str
    success: bool
    final_message: str
    iterations: int
    todo_stats: dict[str, int] | None = None
    error: str | None = None


@dataclass
class AgentLoopWithTodo:
    """
    Agent Loop with TodoWrite

    在基础 Agent Loop 上添加任务追踪能力
    """

    llm: LLMProvider
    registry: ToolRegistry
    store: SQLiteStore
    repo_root: str
    config: AgentLoopWithTodoConfig = field(default_factory=AgentLoopWithTodoConfig)

    def run(
        self,
        *,
        user_goal: str,
        permission_mode: str = "write",
        run_id: str | None = None,
        initial_plan: Plan | None = None,
    ) -> AgentLoopWithTodoResult:
        """
        执行 agent loop（带 todo 追踪）

        Args:
            user_goal: 用户目标
            permission_mode: 权限模式
            run_id: 可选的 run_id
            initial_plan: 可选的初始计划（如果提供，会生成 todo 列表）
        """
        if run_id is None:
            run_id = uuid.uuid4().hex

        # 初始化 run
        self.store.create_run(
            run_id,
            created_at=utc_now_iso(),
            metadata={"goal": user_goal, "repo_root": self.repo_root},
        )

        # 初始化 TodoManager（如果提供了 plan）
        todo_manager: TodoManager | None = None
        if self.config.enable_todo and initial_plan:
            todo_manager = TodoManager.from_plan(initial_plan)
            self.store.append_event(
                run_id=run_id,
                kind="todo_initialized",
                ts=utc_now_iso(),
                payload={"stats": todo_manager.get_stats()},
            )

        # 构建 system prompt（包含 todo 列表）
        system_prompt = self._build_system_prompt(todo_manager)

        # 初始化 message history
        messages: list[ChatMessage] = []
        if system_prompt:
            messages.append(ChatMessage(role="system", content=system_prompt))
        messages.append(ChatMessage(role="user", content=user_goal))

        # 准备工具 schemas（包含 todo_update）
        tool_schemas = self._build_tool_schemas(todo_manager)

        # 创建 ToolRunner（如果有 todo，注册 todo 工具）
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

                # 检查是否需要 nag reminder
                if todo_manager and todo_manager.should_nag(iterations):
                    nag_message = (
                        "\n\n[REMINDER] Please update your task progress using the todo_update tool. "
                        "This helps track your work and maintain focus."
                    )
                    # 将 nag 注入到最后一条 user 消息
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
                    return AgentLoopWithTodoResult(
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
                    return AgentLoopWithTodoResult(
                        run_id=run_id,
                        success=True,
                        final_message=response.content,
                        iterations=iterations,
                        todo_stats=todo_manager.get_stats() if todo_manager else None,
                    )

                # 执行工具调用
                for tc in response.tool_calls:
                    # 解析参数
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

                    # 调用工具
                    result = runner.call(tc.name, args, call_id=tc.id)

                    # 如果是 todo_update，标记已更新
                    if tc.name == "todo_update" and result.ok and todo_manager:
                        todo_manager.mark_updated(iterations)
                        self.store.append_event(
                            run_id=run_id,
                            kind="todo_updated",
                            ts=utc_now_iso(),
                            payload={"stats": todo_manager.get_stats()},
                        )

                    # 构造工具结果消息
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
            return AgentLoopWithTodoResult(
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
            return AgentLoopWithTodoResult(
                run_id=run_id,
                success=False,
                final_message="",
                iterations=iterations,
                error=str(e),
            )

    def _build_system_prompt(self, todo_manager: TodoManager | None) -> str:
        """构建 system prompt（包含 todo 列表）"""
        base_prompt = self.config.system_prompt or ""

        if todo_manager:
            todo_section = "\n\n" + todo_manager.render_for_prompt()
            todo_section += "\n\nIMPORTANT: Use the todo_update tool to mark tasks as in_progress or completed as you work."
            return base_prompt + todo_section

        return base_prompt

    def _build_tool_schemas(self, todo_manager: TodoManager | None) -> list[ToolSchema]:
        """构建工具 schemas（包含 todo_update）"""
        schemas: list[ToolSchema] = []

        # 添加所有注册的工具
        for spec in self.registry.list_specs():
            schemas.append(
                ToolSchema(
                    name=spec.name,
                    description=spec.description,
                    input_schema=spec.input_schema,
                )
            )

        # 如果有 todo_manager，添加 todo_update 工具
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
        """格式化工具结果为字符串"""
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
