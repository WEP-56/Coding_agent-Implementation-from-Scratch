"""
Context Manager - 上下文管理与压缩

实现三层压缩策略：
1. Micro-compact: 自动替换旧工具结果为占位符
2. Auto-compact: Token 超过阈值时 LLM 生成摘要
3. Manual compact: 用户/agent 主动触发压缩
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from codinggirl.runtime.llm_adapter.base import LLMProvider
from codinggirl.runtime.llm_adapter.models import ChatMessage


@dataclass
class ContextStats:
    """上下文统计信息"""

    message_count: int
    token_count: int
    tool_result_count: int
    compact_count: int
    last_compact_iteration: int = 0


@dataclass
class ContextManager:
    """
    Context Manager - 管理对话上下文，防止 overflow

    三层压缩策略：
    1. Micro-compact: 每轮自动替换旧工具结果（保留最近 N 个）
    2. Auto-compact: Token 超过阈值时生成摘要
    3. Manual compact: 主动触发压缩
    """

    keep_recent_results: int = 3  # Micro-compact 保留最近 N 个工具结果
    token_threshold: int = 50000  # Auto-compact 触发阈值
    compact_count: int = field(default=0, init=False)

    def micro_compact(self, messages: list[ChatMessage]) -> tuple[list[ChatMessage], dict[str, Any]]:
        """
        Layer 1 - Micro-compact

        自动替换旧工具结果为占位符，保留最近 N 个完整结果

        Returns:
            (compacted_messages, stats)
        """
        # 找出所有 tool result 消息的索引
        tool_result_indices: list[int] = []
        for i, msg in enumerate(messages):
            if msg.role == "tool":
                tool_result_indices.append(i)

        # 如果工具结果少于等于保留数量，不需要压缩
        if len(tool_result_indices) <= self.keep_recent_results:
            return messages, {
                "compacted": False,
                "tool_result_count": len(tool_result_indices),
                "kept_count": len(tool_result_indices),
            }

        # 确定需要压缩的索引（保留最近 N 个）
        to_compact = set(tool_result_indices[: -self.keep_recent_results])

        # 执行压缩
        compacted: list[ChatMessage] = []
        compacted_count = 0

        for i, msg in enumerate(messages):
            if i in to_compact:
                # 替换为占位符
                compacted.append(
                    ChatMessage(
                        role="tool",
                        content=f"[Compacted tool result: {msg.tool_call_id or 'unknown'}]",
                        tool_call_id=msg.tool_call_id,
                    )
                )
                compacted_count += 1
            else:
                compacted.append(msg)

        self.compact_count += 1

        return compacted, {
            "compacted": True,
            "tool_result_count": len(tool_result_indices),
            "kept_count": self.keep_recent_results,
            "compacted_count": compacted_count,
            "saved_tokens": self._estimate_saved_tokens(messages, compacted),
        }

    def auto_compact(
        self,
        messages: list[ChatMessage],
        llm: LLMProvider,
        run_id: str,
    ) -> tuple[list[ChatMessage], dict[str, Any]]:
        """
        Layer 2 - Auto-compact

        Token 超过阈值时，调用 LLM 生成摘要并替换 messages

        Returns:
            (compacted_messages, stats)
        """
        token_count = self.estimate_tokens(messages)

        # 如果未超过阈值，不压缩
        if token_count < self.token_threshold:
            return messages, {
                "compacted": False,
                "token_count": token_count,
                "threshold": self.token_threshold,
            }

        # 生成摘要
        summary = self._generate_summary(messages, llm)

        # 保留 system prompt（如果有）和最后一条消息
        system_msg = None
        if messages and messages[0].role == "system":
            system_msg = messages[0]

        tail_msgs = self._tail_preserving_tool_pairs(messages)

        # 构建压缩后的 messages
        compacted: list[ChatMessage] = []

        if system_msg:
            compacted.append(system_msg)

        # 添加摘要
        compacted.append(
            ChatMessage(
                role="system",
                content=f"## Conversation Summary (auto-compacted)\n\n{summary}",
            )
        )

        # 保留 tail messages，避免将 tool output 与 tool_call 分离，导致 OpenAI-compatible 400
        for msg in tail_msgs:
            if msg.role == "system":
                continue
            compacted.append(msg)

        self.compact_count += 1

        return compacted, {
            "compacted": True,
            "token_count_before": token_count,
            "token_count_after": self.estimate_tokens(compacted),
            "threshold": self.token_threshold,
            "summary_length": len(summary),
            "saved_tokens": token_count - self.estimate_tokens(compacted),
        }

    def estimate_tokens(self, messages: list[ChatMessage]) -> int:
        """
        估算 token 数量

        简单估算：字符数 / 4
        （对于英文文本，平均 1 token ≈ 4 字符）
        """
        total_chars = 0
        for msg in messages:
            total_chars += len(msg.content)
            if msg.name:
                total_chars += len(msg.name)
            if msg.tool_call_id:
                total_chars += len(msg.tool_call_id)
            # 计算 tool_calls 的内容
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    total_chars += len(tc.id)
                    total_chars += len(tc.name)
                    total_chars += len(tc.arguments_json)

        return total_chars // 4

    def get_stats(self, messages: list[ChatMessage]) -> ContextStats:
        """获取当前上下文统计信息"""
        tool_result_count = sum(1 for msg in messages if msg.role == "tool")

        return ContextStats(
            message_count=len(messages),
            token_count=self.estimate_tokens(messages),
            tool_result_count=tool_result_count,
            compact_count=self.compact_count,
        )

    def should_auto_compact(self, messages: list[ChatMessage]) -> bool:
        """检查是否应该触发 auto-compact"""
        return self.estimate_tokens(messages) >= self.token_threshold

    def _generate_summary(self, messages: list[ChatMessage], llm: LLMProvider) -> str:
        """
        调用 LLM 生成对话摘要

        摘要应该包含：
        1. 用户的主要目标
        2. 已完成的关键操作
        3. 当前状态和上下文
        """
        # 构建摘要 prompt
        summary_prompt = self._build_summary_prompt(messages)

        # 调用 LLM
        try:
            response = llm.chat(
                messages=[
                    ChatMessage(
                        role="system",
                        content="You are a helpful assistant that summarizes conversations concisely.",
                    ),
                    ChatMessage(role="user", content=summary_prompt),
                ],
                temperature=0.0,
            )
            return response.content
        except Exception as e:
            # 如果 LLM 调用失败，返回简单摘要
            return f"[Auto-compact failed: {e}. Message count: {len(messages)}]"

    def _build_summary_prompt(self, messages: list[ChatMessage]) -> str:
        """构建摘要 prompt"""
        # 提取关键信息
        user_messages = [msg.content for msg in messages if msg.role == "user"]
        assistant_messages = [msg.content for msg in messages if msg.role == "assistant"]
        tool_calls = [msg.tool_call_id for msg in messages if msg.role == "tool"]

        prompt = f"""Please summarize the following conversation concisely (max 500 words).

Focus on:
1. The user's main goal
2. Key actions taken (tools called, files modified, etc.)
3. Current state and important context

Conversation stats:
- Total messages: {len(messages)}
- User messages: {len(user_messages)}
- Assistant messages: {len(assistant_messages)}
- Tool calls: {len(tool_calls)}

Recent messages (last 5):
"""
        # 添加最近 5 条消息
        for msg in messages[-5:]:
            role = msg.role
            content = msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
            prompt += f"\n{role}: {content}"

        return prompt

    def _tail_preserving_tool_pairs(self, messages: list[ChatMessage]) -> list[ChatMessage]:
        """
        Preserve a tail window of messages while keeping tool call pairs intact.

        Some OpenAI-compatible servers validate that a tool result references a previously
        declared tool call id in an assistant message. If auto-compact keeps only a tool
        result (or drops its corresponding assistant tool_calls), the request becomes invalid.
        """
        if not messages:
            return []

        default_keep = 6
        start = max(0, len(messages) - default_keep)

        def has_tool_call_id(assistant: ChatMessage, call_id: str) -> bool:
            if assistant.role != "assistant" or not assistant.tool_calls:
                return False
            return any(tc.id == call_id for tc in assistant.tool_calls)

        changed = True
        while changed:
            changed = False
            for i in range(start, len(messages)):
                msg = messages[i]
                if msg.role != "tool" or not msg.tool_call_id:
                    continue
                call_id = msg.tool_call_id
                parent = None
                for j in range(i - 1, -1, -1):
                    if has_tool_call_id(messages[j], call_id):
                        parent = j
                        break
                if parent is not None and parent < start:
                    start = parent
                    changed = True

        # Also keep the closest user message before the tool-call assistant (usually the prompt).
        if start > 0:
            for j in range(start - 1, -1, -1):
                if messages[j].role == "user":
                    start = j
                    break
                if messages[j].role == "assistant":
                    break

        return messages[start:]

    def _estimate_saved_tokens(
        self, original: list[ChatMessage], compacted: list[ChatMessage]
    ) -> int:
        """估算节省的 token 数"""
        return self.estimate_tokens(original) - self.estimate_tokens(compacted)
