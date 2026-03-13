"""
Tests for Subagent Runner
"""
from __future__ import annotations

import pytest

from codinggirl.core.contracts import Plan, PlanStep
from codinggirl.core.subagent_runner import SubagentConfig, SubagentRunner
from codinggirl.runtime.defaults import create_default_registry
from codinggirl.runtime.llm_adapter.mock_provider import MockProvider
from codinggirl.runtime.llm_adapter.models import LLMConfig, LLMResponse, ToolCall
from codinggirl.runtime.storage_sqlite import SQLiteStore
from codinggirl.runtime.workspace import RepoWorkspace


def test_subagent_basic_execution():
    """测试子 agent 基本执行流程"""
    # 准备
    ws = RepoWorkspace.from_path(".")
    registry = create_default_registry(ws)
    store = SQLiteStore(db_path=":memory:")
    store.init_schema()

    # 创建 mock LLM（模拟子 agent 的响应）
    llm = MockProvider(config=LLMConfig(provider="mock", model="mock"))
    llm.add_response(
        LLMResponse(
            model="mock",
            content="I found 3 Python files in the core directory.",
            finish_reason="stop",
            tool_calls=[],
        )
    )

    # 创建 SubagentRunner
    runner = SubagentRunner(
        llm=llm,
        registry=registry,
        store=store,
        parent_run_id="test_run",
        config=SubagentConfig(max_iterations=5),
    )

    # 执行
    result = runner.run(
        task_description="Find all Python files in codinggirl/core",
        context=None,
    )

    # 验证
    assert result.success
    assert "3 Python files" in result.summary
    assert result.iterations == 1
    assert result.tool_calls_count == 0


def test_subagent_with_tool_calls():
    """测试子 agent 调用工具"""
    ws = RepoWorkspace.from_path(".")
    registry = create_default_registry(ws)
    store = SQLiteStore(db_path=":memory:")
    store.init_schema()

    # 创建 mock LLM
    llm = MockProvider(config=LLMConfig(provider="mock", model="mock"))

    # 第一轮：调用 fs_glob
    llm.add_response(
        LLMResponse(
            model="mock",
            content="Let me search for Python files.",
            finish_reason="tool_use",
            tool_calls=[
                ToolCall(
                    id="call_1",
                    name="fs_glob",
                    arguments_json='{"pattern": "codinggirl/core/*.py"}',
                )
            ],
        )
    )

    # 第二轮：返回结果
    llm.add_response(
        LLMResponse(
            model="mock",
            content="Found 10 Python files in codinggirl/core directory.",
            finish_reason="stop",
            tool_calls=[],
        )
    )

    runner = SubagentRunner(
        llm=llm,
        registry=registry,
        store=store,
        parent_run_id="test_run",
        config=SubagentConfig(max_iterations=5),
    )

    result = runner.run(
        task_description="Find all Python files in codinggirl/core",
        context=None,
    )

    assert result.success
    assert result.iterations == 2
    assert result.tool_calls_count == 1


def test_subagent_tool_restriction():
    """测试子 agent 工具限制"""
    ws = RepoWorkspace.from_path(".")
    registry = create_default_registry(ws)
    store = SQLiteStore(db_path=":memory:")
    store.init_schema()

    llm = MockProvider(config=LLMConfig(provider="mock", model="mock"))

    # 尝试调用不允许的工具（fs_write_file）
    llm.add_response(
        LLMResponse(
            model="mock",
            content="Let me write a file.",
            finish_reason="tool_use",
            tool_calls=[
                ToolCall(
                    id="call_1",
                    name="fs_write_file",
                    arguments_json='{"path": "test.txt", "content": "test"}',
                )
            ],
        )
    )

    # 第二轮：收到错误后返回
    llm.add_response(
        LLMResponse(
            model="mock",
            content="I cannot write files. Task failed.",
            finish_reason="stop",
            tool_calls=[],
        )
    )

    runner = SubagentRunner(
        llm=llm,
        registry=registry,
        store=store,
        parent_run_id="test_run",
        config=SubagentConfig(max_iterations=5),
    )

    result = runner.run(
        task_description="Write a test file",
        context=None,
    )

    # 子 agent 应该完成（虽然任务失败）
    assert result.success
    assert "cannot write files" in result.summary.lower()


def test_subagent_max_iterations():
    """测试子 agent 达到最大迭代次数"""
    ws = RepoWorkspace.from_path(".")
    registry = create_default_registry(ws)
    store = SQLiteStore(db_path=":memory:")
    store.init_schema()

    llm = MockProvider(config=LLMConfig(provider="mock", model="mock"))

    # 每轮都调用工具，永不结束
    for i in range(10):
        llm.add_response(
            LLMResponse(
                model="mock",
                content="Let me search more.",
                finish_reason="tool_use",
                tool_calls=[
                    ToolCall(
                        id=f"call_{i}",
                        name="fs_glob",
                        arguments_json='{"pattern": "*.py"}',
                    )
                ],
            )
        )

    runner = SubagentRunner(
        llm=llm,
        registry=registry,
        store=store,
        parent_run_id="test_run",
        config=SubagentConfig(max_iterations=3),
    )

    result = runner.run(
        task_description="Find all files",
        context=None,
    )

    # 应该失败（达到最大迭代次数）
    assert not result.success
    assert result.iterations == 3
    assert "max iterations" in result.error.lower()


def test_subagent_with_context():
    """测试子 agent 接收父 agent 的上下文"""
    ws = RepoWorkspace.from_path(".")
    registry = create_default_registry(ws)
    store = SQLiteStore(db_path=":memory:")
    store.init_schema()

    llm = MockProvider(config=LLMConfig(provider="mock", model="mock"))
    llm.add_response(
        LLMResponse(
            model="mock",
            content="Based on the context, I found the relevant files.",
            finish_reason="stop",
            tool_calls=[],
        )
    )

    runner = SubagentRunner(
        llm=llm,
        registry=registry,
        store=store,
        parent_run_id="test_run",
        config=SubagentConfig(max_iterations=5),
    )

    result = runner.run(
        task_description="Find test files",
        context="Focus on the tests/ directory",
    )

    assert result.success
    assert "found" in result.summary.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
