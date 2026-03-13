"""
Agent Loop - 核心自主循环实现

基于 Claude Code 教程的架构理念：
- while stop_reason == "tool_use" 循环
- message history 作为单一事实源
- 工具调度与结果累积
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from codinggirl.core.contracts import ToolCall as ContractToolCall
from codinggirl.core.contracts import ToolResult, utc_now_iso
from codinggirl.core.policy import PermissionPolicy
from codinggirl.runtime.llm_adapter.base import LLMProvider
from codinggirl.runtime.llm_adapter.models import ChatMessage, ToolSchema
from codinggirl.runtime.storage_sqlite import SQLiteStore
from codinggirl.runtime.tools.registry import ToolRegistry
from codinggirl.runtime.tools.runner import ToolRunner


@dataclass
class AgentLoopConfig:
    """Agent Loop 配置"""

    max_iterations: int = 50  # 最大循环次数（防止无限循环）
    temperature: float = 0.0  # LLM 温度
    system_prompt: str | None = None  # 系统提示词


@dataclass
class AgentLoopResult:
    """Agent Loop 执行结果"""

    run_id: str
    success: bool
    final_message: str
    iterations: int
    error: str | None = None


@dataclass
class AgentLoop:
    """
    Agent Loop 核心类

    实现 "while stop_reason == 'tool_use'" 循环：
    1. 用户输入 → messages
    2. LLM 生成响应（可能包含 tool_calls）
    3. 如果有 tool_calls，执行工具并追加结果到 messages
    4. 循环直到 LLM 返回最终答案（stop_reason != 'tool_use'）
    """

    llm: LLMProvider
    registry: ToolRegistry
    store: SQLiteStore
    repo_root: str
    config: AgentLoopConfig = field(default_factory=AgentLoopConfig)

    def run(
        self,
        *,
        user_goal: str,
        permission_mode: str = "write",
        run_id: str | None = None,
    ) -> AgentLoopResult:
        """
        执行 agent loop

        Args:
            user_goal: 用户目标/问题
            permission_mode: 权限模式（readonly/write/exec）
            run_id: 可选的 run_id（用于恢复）

        Returns:
            AgentLoopResult
        """
        if run_id is None:
            run_id = uuid.uuid4().hex

        # 初始化 run
        self.store.create_run(
            run_id,
            created_at=utc_now_iso(),
            metadata={"goal": user_goal, "repo_root": self.repo_root},
        )

        # 初始化 message history
        messages: list[ChatMessage] = []

        # 添加 system prompt
        if self.config.system_prompt:
            messages.append(ChatMessage(role="system", content=self.config.system_prompt))

        # 添加用户目标
        messages.append(ChatMessage(role="user", content=user_goal))

        # 准备工具 schemas
        tool_schemas = self._build_tool_schemas()

        # 创建 ToolRunner
        permission = PermissionPolicy(mode=permission_mode)  # type: ignore[arg-type]
        runner = ToolRunner(
            registry=self.registry,
            store=self.store,
            run_id=run_id,
            permission=permission,
        )

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

                # 调用 LLM
                try:
                    response = self.llm.chat(
                        messages=messages,
                        tools=tool_schemas,
                        temperature=self.config.temperature,
                    )
                except Exception as e:
                    return AgentLoopResult(
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

                # 将 assistant 消息追加到 history（包含 tool_calls）
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
                    return AgentLoopResult(
                        run_id=run_id,
                        success=True,
                        final_message=response.content,
                        iterations=iterations,
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
            return AgentLoopResult(
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
            return AgentLoopResult(
                run_id=run_id,
                success=False,
                final_message="",
                iterations=iterations,
                error=str(e),
            )

    def _build_tool_schemas(self) -> list[ToolSchema]:
        """从 ToolRegistry 构建 LLM 工具 schemas"""
        schemas: list[ToolSchema] = []
        for spec in self.registry.list_specs():
            schemas.append(
                ToolSchema(
                    name=spec.name,
                    description=spec.description,
                    input_schema=spec.input_schema,
                )
            )
        return schemas

    def _format_tool_result(self, result: ToolResult) -> str:
        """格式化工具结果为字符串（供 LLM 消费）"""
        if not result.ok:
            return f"Error: {result.error}"

        parts: list[str] = []

        # 添加 content
        if result.content:
            if isinstance(result.content, dict):
                parts.append(json.dumps(result.content, ensure_ascii=False, indent=2))
            else:
                parts.append(str(result.content))

        # 添加 stdout
        if result.stdout:
            parts.append(f"stdout:\n{result.stdout}")

        # 添加 stderr
        if result.stderr:
            parts.append(f"stderr:\n{result.stderr}")

        return "\n\n".join(parts) if parts else "Success (no output)"
