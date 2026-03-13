"""
Subagent Runner - 子 Agent 执行器

实现任务委托机制：
1. 父 agent 通过 task 工具委托子任务
2. 子 agent 在独立的 message history 中执行
3. 子 agent 只能使用基础工具（不能再创建子 agent）
4. 返回摘要给父 agent
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field

from codinggirl.core.contracts import ToolResult, utc_now_iso
from codinggirl.core.policy import PermissionPolicy
from codinggirl.runtime.llm_adapter.base import LLMProvider
from codinggirl.runtime.llm_adapter.models import ChatMessage, ToolSchema
from codinggirl.runtime.storage_sqlite import SQLiteStore
from codinggirl.runtime.tools.registry import ToolRegistry
from codinggirl.runtime.tools.runner import ToolRunner


@dataclass
class SubagentConfig:
    """子 Agent 配置"""

    max_iterations: int = 20  # 子 agent 迭代次数限制（比父 agent 少）
    temperature: float = 0.0
    allowed_tools: set[str] = field(
        default_factory=lambda: {
            "fs_read_file",
            "fs_glob",
            "search_rg",
            "index_query_repo_map",
            "index_query_imports",
        }
    )  # 子 agent 只能用只读工具


@dataclass
class SubagentResult:
    """子 Agent 执行结果"""

    success: bool
    summary: str  # 给父 agent 的摘要
    iterations: int
    error: str | None = None
    tool_calls_count: int = 0


class SubagentRunner:
    """
    Subagent Runner - 执行委托的子任务

    设计原则：
    1. 独立的 message history（不污染父 agent 上下文）
    2. 工具限制（只能用只读工具，不能递归创建子 agent）
    3. 自动摘要（返回简洁的结果给父 agent）
    """

    def __init__(
        self,
        llm: LLMProvider,
        registry: ToolRegistry,
        store: SQLiteStore,
        parent_run_id: str,
        config: SubagentConfig | None = None,
    ):
        self.llm = llm
        self.registry = registry
        self.store = store
        self.parent_run_id = parent_run_id
        self.config = config or SubagentConfig()

    def run(
        self,
        task_description: str,
        context: str | None = None,
    ) -> SubagentResult:
        """
        执行子任务

        Args:
            task_description: 任务描述
            context: 父 agent 提供的上下文（可选）

        Returns:
            SubagentResult
        """
        subagent_id = uuid.uuid4().hex

        # 记录子 agent 启动
        self.store.append_event(
            run_id=self.parent_run_id,
            kind="subagent_start",
            ts=utc_now_iso(),
            payload={
                "subagent_id": subagent_id,
                "task": task_description,
                "context": context,
            },
        )

        # 构建 system prompt
        system_prompt = self._build_system_prompt(task_description, context)

        # 初始化 message history
        messages: list[ChatMessage] = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=task_description),
        ]

        # 准备工具 schemas（只包含允许的工具）
        tool_schemas = self._build_tool_schemas()

        # 创建 ToolRunner（只读权限）
        permission = PermissionPolicy(mode="readonly")
        runner = ToolRunner(
            registry=self.registry,
            store=self.store,
            run_id=self.parent_run_id,  # 使用父 run_id，方便追踪
            permission=permission,
        )

        # 主循环
        iterations = 0
        tool_calls_count = 0

        try:
            while iterations < self.config.max_iterations:
                iterations += 1

                # 调用 LLM
                try:
                    response = self.llm.chat(
                        messages=messages,
                        tools=tool_schemas,
                        temperature=self.config.temperature,
                    )
                except Exception as e:
                    return SubagentResult(
                        success=False,
                        summary="",
                        iterations=iterations,
                        error=f"LLM call failed: {e}",
                    )

                # 追加 assistant 消息
                messages.append(
                    ChatMessage(
                        role="assistant",
                        content=response.content,
                        tool_calls=response.tool_calls if response.tool_calls else None,
                    )
                )

                # 检查是否有 tool_calls
                if not response.tool_calls:
                    # 没有工具调用，子任务完成
                    summary = self._extract_summary(response.content)

                    self.store.append_event(
                        run_id=self.parent_run_id,
                        kind="subagent_complete",
                        ts=utc_now_iso(),
                        payload={
                            "subagent_id": subagent_id,
                            "iterations": iterations,
                            "tool_calls_count": tool_calls_count,
                            "summary": summary,
                        },
                    )

                    return SubagentResult(
                        success=True,
                        summary=summary,
                        iterations=iterations,
                        tool_calls_count=tool_calls_count,
                    )

                # 执行工具调用
                for tc in response.tool_calls:
                    tool_calls_count += 1

                    # 检查工具是否允许
                    if tc.name not in self.config.allowed_tools:
                        result_content = f"Error: Tool '{tc.name}' is not allowed in subagent context. Allowed tools: {', '.join(self.config.allowed_tools)}"
                        messages.append(
                            ChatMessage(
                                role="tool",
                                content=result_content,
                                tool_call_id=tc.id,
                            )
                        )
                        continue

                    try:
                        args = json.loads(tc.arguments_json)
                    except json.JSONDecodeError:
                        args = {}

                    result = runner.call(tc.name, args, call_id=tc.id)
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
                run_id=self.parent_run_id,
                kind="subagent_max_iterations",
                ts=utc_now_iso(),
                payload={
                    "subagent_id": subagent_id,
                    "iterations": iterations,
                },
            )

            # 尝试从最后的 assistant 消息提取摘要
            last_content = ""
            for msg in reversed(messages):
                if msg.role == "assistant":
                    last_content = msg.content
                    break

            summary = self._extract_summary(last_content) if last_content else "Task incomplete (max iterations reached)"

            return SubagentResult(
                success=False,
                summary=summary,
                iterations=iterations,
                error=f"Reached max iterations ({self.config.max_iterations})",
                tool_calls_count=tool_calls_count,
            )

        except Exception as e:
            self.store.append_event(
                run_id=self.parent_run_id,
                kind="subagent_error",
                ts=utc_now_iso(),
                payload={
                    "subagent_id": subagent_id,
                    "error": str(e),
                    "iterations": iterations,
                },
            )

            return SubagentResult(
                success=False,
                summary="",
                iterations=iterations,
                error=str(e),
                tool_calls_count=tool_calls_count,
            )

    def _build_system_prompt(self, task: str, context: str | None) -> str:
        """构建子 agent 的 system prompt"""
        prompt = f"""You are a subagent helping with a specific research task.

Your task: {task}

Available tools (read-only):
- fs_read_file: Read file contents
- fs_glob: Find files by pattern
- search_rg: Search text in files
- index_query_repo_map: Query repository structure
- index_query_imports: Query import relationships

Guidelines:
1. Focus on the specific task assigned to you
2. Use tools to gather information
3. Be concise and direct
4. When you have enough information, provide a clear summary
5. Do NOT try to modify files or run commands

"""
        if context:
            prompt += f"\nContext from parent agent:\n{context}\n"

        return prompt

    def _build_tool_schemas(self) -> list[ToolSchema]:
        """构建工具 schemas（只包含允许的工具）"""
        schemas: list[ToolSchema] = []

        for spec in self.registry.list_specs():
            if spec.name in self.config.allowed_tools:
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

    def _extract_summary(self, content: str) -> str:
        """
        从 assistant 消息中提取摘要

        简单策略：取前 500 字符
        """
        if len(content) <= 500:
            return content

        return content[:500] + "..."
