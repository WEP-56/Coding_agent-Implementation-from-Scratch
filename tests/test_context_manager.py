"""
Context Manager 测试
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from codinggirl.core.context_manager import ContextManager
from codinggirl.runtime.llm_adapter.models import ChatMessage, LLMConfig, LLMResponse
from codinggirl.runtime.llm_adapter.mock_provider import MockProvider


def test_micro_compact_basic():
    """测试：Micro-compact 基础功能"""
    manager = ContextManager(keep_recent_results=2)

    # 创建包含 5 个工具结果的消息列表
    messages = [
        ChatMessage(role="user", content="Task 1"),
        ChatMessage(role="assistant", content="OK"),
        ChatMessage(role="tool", content="Result 1", tool_call_id="call_1"),
        ChatMessage(role="assistant", content="OK"),
        ChatMessage(role="tool", content="Result 2", tool_call_id="call_2"),
        ChatMessage(role="assistant", content="OK"),
        ChatMessage(role="tool", content="Result 3", tool_call_id="call_3"),
        ChatMessage(role="assistant", content="OK"),
        ChatMessage(role="tool", content="Result 4", tool_call_id="call_4"),
        ChatMessage(role="assistant", content="OK"),
        ChatMessage(role="tool", content="Result 5", tool_call_id="call_5"),
    ]

    # 执行压缩
    compacted, stats = manager.micro_compact(messages)

    # 验证
    assert stats["compacted"] is True
    assert stats["tool_result_count"] == 5
    assert stats["kept_count"] == 2
    assert stats["compacted_count"] == 3

    # 验证最近 2 个结果保留完整
    tool_results = [msg for msg in compacted if msg.role == "tool"]
    assert len(tool_results) == 5
    assert "Result 4" in tool_results[-2].content
    assert "Result 5" in tool_results[-1].content

    # 验证旧结果被压缩
    assert "[Compacted tool result:" in tool_results[0].content

    print(f"[+] Micro-compact test passed: {stats}")


def test_micro_compact_no_compression_needed():
    """测试：工具结果少于保留数量时不压缩"""
    manager = ContextManager(keep_recent_results=3)

    messages = [
        ChatMessage(role="user", content="Task"),
        ChatMessage(role="tool", content="Result 1", tool_call_id="call_1"),
        ChatMessage(role="tool", content="Result 2", tool_call_id="call_2"),
    ]

    compacted, stats = manager.micro_compact(messages)

    assert stats["compacted"] is False
    assert len(compacted) == len(messages)


def test_token_estimation():
    """测试：Token 估算"""
    manager = ContextManager()

    messages = [
        ChatMessage(role="user", content="Hello world"),  # ~11 chars = ~2-3 tokens
        ChatMessage(role="assistant", content="Hi there"),  # ~8 chars = ~2 tokens
    ]

    token_count = manager.estimate_tokens(messages)

    # 简单验证：应该在合理范围内
    assert token_count > 0
    assert token_count < 100  # 不应该太大

    print(f"[+] Token estimation: {token_count} tokens for {len(messages)} messages")


def test_auto_compact_trigger():
    """测试：Auto-compact 触发条件"""
    manager = ContextManager(token_threshold=100)

    # 创建一个小消息列表（不触发）
    small_messages = [
        ChatMessage(role="user", content="Hi"),
        ChatMessage(role="assistant", content="Hello"),
    ]

    assert manager.should_auto_compact(small_messages) is False

    # 创建一个大消息列表（触发）
    large_messages = [
        ChatMessage(role="user", content="x" * 500),  # ~125 tokens
    ]

    assert manager.should_auto_compact(large_messages) is True


def test_auto_compact_with_mock_llm():
    """测试：Auto-compact 使用 mock LLM"""
    manager = ContextManager(token_threshold=50)

    # 创建超过阈值的消息
    messages = [
        ChatMessage(role="system", content="You are a helpful assistant"),
        ChatMessage(role="user", content="x" * 300),  # ~75 tokens
        ChatMessage(role="assistant", content="OK"),
        ChatMessage(role="tool", content="Result", tool_call_id="call_1"),
    ]

    # Mock LLM
    llm_config = LLMConfig(provider="mock", model="test")
    llm = MockProvider(config=llm_config)
    llm.set_next_response(
        LLMResponse(
            model="test",
            content="Summary: User asked a question, assistant responded.",
            finish_reason="stop",
        )
    )

    # 执行压缩
    compacted, stats = manager.auto_compact(messages, llm, run_id="test_run")

    # 验证
    assert stats["compacted"] is True
    assert stats["token_count_before"] > stats["token_count_after"]
    assert stats["saved_tokens"] > 0

    # 验证压缩后的结构
    assert len(compacted) >= 2  # 至少有 system + summary
    assert any("Summary" in msg.content for msg in compacted)

    print(f"[+] Auto-compact test passed: {stats}")


def test_context_stats():
    """测试：获取上下文统计"""
    manager = ContextManager()

    messages = [
        ChatMessage(role="user", content="Task"),
        ChatMessage(role="assistant", content="OK"),
        ChatMessage(role="tool", content="Result 1", tool_call_id="call_1"),
        ChatMessage(role="tool", content="Result 2", tool_call_id="call_2"),
    ]

    stats = manager.get_stats(messages)

    assert stats.message_count == 4
    assert stats.tool_result_count == 2
    assert stats.token_count > 0
    assert stats.compact_count == 0

    print(f"[+] Context stats: {stats}")


if __name__ == "__main__":
    test_micro_compact_basic()
    test_micro_compact_no_compression_needed()
    test_token_estimation()
    test_auto_compact_trigger()
    test_auto_compact_with_mock_llm()
    test_context_stats()
    print("\n[+] All Context Manager tests passed!")
