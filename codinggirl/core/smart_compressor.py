"""
智能上下文压缩器

基于消息重要性的智能压缩策略
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from codinggirl.runtime.llm_adapter.models import ChatMessage


@dataclass
class MessageImportance:
    """消息重要性评分"""

    index: int
    role: str
    importance_score: float  # 0-1
    reason: str
    token_count: int


class SmartCompressor:
    """
    智能压缩器

    根据消息重要性选择性压缩，而不是简单的时间窗口
    """

    def __init__(self):
        self.importance_weights = {
            "has_error": 2.0,  # 包含错误信息
            "has_file_path": 1.5,  # 包含文件路径
            "has_code": 1.3,  # 包含代码
            "is_recent": 1.5,  # 最近的消息
            "is_user": 1.2,  # 用户消息
            "is_system": 2.0,  # 系统消息（通常很重要）
            "has_todo": 1.8,  # 包含 todo 信息
            "is_tool_result": 0.8,  # 工具结果（相对不重要）
        }

    def calculate_importance(
        self,
        msg: ChatMessage,
        index: int,
        total: int,
    ) -> MessageImportance:
        """
        计算消息的重要性评分

        Args:
            msg: 消息
            index: 消息索引
            total: 总消息数

        Returns:
            MessageImportance
        """
        score = 1.0
        reasons: list[str] = []

        content = msg.content.lower()

        # 1. 角色权重
        if msg.role == "system":
            score *= self.importance_weights["is_system"]
            reasons.append("system")
        elif msg.role == "user":
            score *= self.importance_weights["is_user"]
            reasons.append("user")
        elif msg.role == "tool":
            score *= self.importance_weights["is_tool_result"]

        # 2. 内容特征
        if any(word in content for word in ["error", "failed", "exception", "traceback"]):
            score *= self.importance_weights["has_error"]
            reasons.append("has_error")

        if re.search(r'\.(py|js|ts|java|go|rs|cpp|c|h)\b', content):
            score *= self.importance_weights["has_file_path"]
            reasons.append("has_file_path")

        if "```" in msg.content or re.search(r'(def |class |function |import |from )', content):
            score *= self.importance_weights["has_code"]
            reasons.append("has_code")

        if "todo" in content or "task" in content:
            score *= self.importance_weights["has_todo"]
            reasons.append("has_todo")

        # 3. 位置权重（最近的消息更重要）
        recency = (index + 1) / total  # 0-1
        if recency > 0.8:  # 最近 20%
            score *= self.importance_weights["is_recent"]
            reasons.append("recent")

        # 4. 长度惩罚（过长的消息可能是冗余的工具输出）
        token_count = len(msg.content) // 4
        if token_count > 2000:
            score *= 0.7
            reasons.append("too_long")

        return MessageImportance(
            index=index,
            role=msg.role,
            importance_score=score,
            reason=", ".join(reasons) if reasons else "default",
            token_count=token_count,
        )

    def smart_compact(
        self,
        messages: list[ChatMessage],
        target_token_count: int,
    ) -> tuple[list[ChatMessage], dict[str, Any]]:
        """
        智能压缩到目标 token 数

        策略：
        1. 计算所有消息的重要性
        2. 保留高重要性消息
        3. 压缩低重要性消息

        Args:
            messages: 消息列表
            target_token_count: 目标 token 数

        Returns:
            (compacted_messages, stats)
        """
        if not messages:
            return messages, {"compacted": False}

        # 计算所有消息的重要性
        importances = [
            self.calculate_importance(msg, i, len(messages))
            for i, msg in enumerate(messages)
        ]

        # 当前 token 总数
        current_tokens = sum(imp.token_count for imp in importances)

        if current_tokens <= target_token_count:
            return messages, {
                "compacted": False,
                "current_tokens": current_tokens,
                "target_tokens": target_token_count,
            }

        # 需要删除的 token 数
        tokens_to_remove = current_tokens - target_token_count

        # 按重要性排序（从低到高）
        sorted_importances = sorted(importances, key=lambda x: x.importance_score)

        # 选择要压缩的消息
        to_compact: set[int] = set()
        removed_tokens = 0

        for imp in sorted_importances:
            # 保护 system 消息和最后几条消息
            if imp.role == "system" or imp.index >= len(messages) - 3:
                continue

            to_compact.add(imp.index)
            removed_tokens += imp.token_count

            if removed_tokens >= tokens_to_remove:
                break

        # 执行压缩
        compacted: list[ChatMessage] = []
        for i, msg in enumerate(messages):
            if i in to_compact:
                # 压缩为摘要
                summary = self._summarize_message(msg)
                compacted.append(
                    ChatMessage(
                        role=msg.role,
                        content=summary,
                        tool_call_id=msg.tool_call_id,
                        name=msg.name,
                    )
                )
            else:
                compacted.append(msg)

        final_tokens = sum(len(msg.content) // 4 for msg in compacted)

        return compacted, {
            "compacted": True,
            "messages_compacted": len(to_compact),
            "tokens_before": current_tokens,
            "tokens_after": final_tokens,
            "tokens_saved": current_tokens - final_tokens,
            "target_tokens": target_token_count,
        }

    def _summarize_message(self, msg: ChatMessage) -> str:
        """
        将消息压缩为摘要

        保留关键信息，删除冗余内容
        """
        content = msg.content

        # 如果是工具结果，提取关键信息
        if msg.role == "tool":
            # 提取文件路径
            file_paths = re.findall(r'[\w/\\.-]+\.(py|js|ts|java|go|rs|cpp|c|h)', content)
            # 提取错误信息
            errors = re.findall(r'(error|exception|failed).*', content, re.IGNORECASE)

            summary_parts = []
            if file_paths:
                summary_parts.append(f"Files: {', '.join(set(file_paths[:3]))}")
            if errors:
                summary_parts.append(f"Errors: {errors[0][:100]}")

            if summary_parts:
                return f"[Compacted] {' | '.join(summary_parts)}"
            else:
                return f"[Compacted tool result: {len(content)} chars]"

        # 其他消息，简单截断
        if len(content) > 200:
            return content[:200] + f"... [truncated {len(content) - 200} chars]"

        return content


def estimate_tokens_accurate(messages: list[ChatMessage]) -> int:
    """
    更准确的 token 估算

    考虑不同语言的 token 密度
    """
    total_tokens = 0

    for msg in messages:
        content = msg.content

        # 检测语言
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', content))
        total_chars = len(content)

        if chinese_chars > total_chars * 0.3:
            # 中文为主：1 字符 ≈ 1.5 tokens
            total_tokens += int(total_chars * 1.5)
        else:
            # 英文为主：1 token ≈ 4 字符
            total_tokens += total_chars // 4

        # 添加结构化数据的 token（tool_calls 等）
        if msg.tool_calls:
            for tc in msg.tool_calls:
                total_tokens += len(tc.name) // 4
                total_tokens += len(tc.arguments_json) // 4

    return total_tokens
