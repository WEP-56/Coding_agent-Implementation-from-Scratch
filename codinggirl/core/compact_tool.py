"""
Compact Tool - 手动触发上下文压缩

允许 agent 或用户主动触发上下文压缩
"""
from __future__ import annotations

from typing import Any

from codinggirl.core.context_manager import ContextManager
from codinggirl.runtime.llm_adapter.base import LLMProvider
from codinggirl.runtime.llm_adapter.models import ChatMessage
from codinggirl.runtime.tools.registry import ToolSpec


def create_compact_tool_spec() -> ToolSpec:
    """创建 compact 工具规范"""
    return ToolSpec(
        name="compact_context",
        description=(
            "Manually trigger context compression to reduce token usage. "
            "Use this when you notice the conversation history is getting too long, "
            "or when you want to summarize progress before starting a new phase of work."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why you are triggering compression (optional)",
                }
            },
            "required": [],
        },
        risk_level="low",
        required_permission=None,
    )


def create_compact_handler(
    context_manager: ContextManager,
    llm: LLMProvider,
    run_id: str,
    get_messages: callable,
    set_messages: callable,
) -> callable:
    """
    创建 compact 工具处理器

    Args:
        context_manager: ContextManager 实例
        llm: LLM provider
        run_id: 当前 run ID
        get_messages: 获取当前 messages 的回调
        set_messages: 设置 messages 的回调
    """

    def handler(reason: str | None = None) -> dict[str, Any]:
        """手动触发压缩"""
        messages = get_messages()

        # 执行 auto-compact
        compacted, stats = context_manager.auto_compact(messages, llm, run_id)

        if stats["compacted"]:
            set_messages(compacted)
            return {
                "ok": True,
                "message": f"Context compressed successfully. Saved ~{stats['saved_tokens']} tokens.",
                "stats": {
                    "token_count_before": stats["token_count_before"],
                    "token_count_after": stats["token_count_after"],
                    "saved_tokens": stats["saved_tokens"],
                    "summary_length": stats["summary_length"],
                },
            }
        else:
            return {
                "ok": False,
                "message": "Context is already compact, no compression needed.",
                "stats": {
                    "token_count": stats["token_count"],
                    "threshold": stats["threshold"],
                },
            }

    return handler
