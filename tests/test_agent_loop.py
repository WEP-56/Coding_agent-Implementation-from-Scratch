"""
Agent Loop 单元测试
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from codinggirl.core.agent_loop import AgentLoop, AgentLoopConfig
from codinggirl.runtime.llm_adapter.models import ChatMessage, LLMConfig, LLMResponse, ToolCall
from codinggirl.runtime.llm_adapter.mock_provider import MockProvider
from codinggirl.runtime.storage_sqlite import SQLiteStore
from codinggirl.runtime.tools.registry import ToolRegistry, ToolSpec
from codinggirl.runtime.workspace import RepoWorkspace


def test_agent_loop_no_tool_calls():
    """测试：LLM 直接返回答案，无工具调用"""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        # 使用内存数据库避免 Windows 文件锁
        db_path = Path(":memory:")

        # 创建组件
        ws = RepoWorkspace.from_path(str(repo_path))
        registry = ToolRegistry()
        store = SQLiteStore(db_path=db_path)
        store.init_schema()

        # Mock LLM：直接返回答案
        llm_config = LLMConfig(provider="mock", model="test")
        llm = MockProvider(config=llm_config)
        llm.set_next_response(
            LLMResponse(
                model="test",
                content="The answer is 42.",
                finish_reason="stop",
                tool_calls=[],
            )
        )

        # 创建 Agent Loop
        loop = AgentLoop(
            llm=llm,
            registry=registry,
            store=store,
            repo_root=str(repo_path),
            config=AgentLoopConfig(system_prompt="You are a helpful assistant."),
        )

        # 执行
        result = loop.run(user_goal="What is the answer?")

        # 验证
        assert result.success is True
        assert result.iterations == 1
        assert result.final_message == "The answer is 42."
        assert result.error is None


def test_agent_loop_with_tool_calls():
    """测试：LLM 调用工具，然后返回答案"""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        db_path = Path(":memory:")

        # 创建测试文件
        test_file = repo_path / "test.txt"
        test_file.write_text("Hello World")

        # 创建组件
        ws = RepoWorkspace.from_path(str(repo_path))
        registry = ToolRegistry()

        # 注册一个简单的读取工具
        from codinggirl.core.contracts import ToolCall as ContractToolCall
        from codinggirl.core.contracts import ToolResult

        def read_handler(call: ContractToolCall) -> ToolResult:
            path = call.args.get("path")
            try:
                content = (repo_path / path).read_text()
                return ToolResult(
                    call_id=call.call_id,
                    tool_name=call.tool_name,
                    ok=True,
                    content={"text": content},
                )
            except Exception as e:
                return ToolResult(
                    call_id=call.call_id,
                    tool_name=call.tool_name,
                    ok=False,
                    error=str(e),
                )

        registry.register(
            ToolSpec(
                name="read_file",
                description="Read a file",
                input_schema={
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            ),
            read_handler,
        )

        store = SQLiteStore(db_path=db_path)
        store.init_schema()

        # Mock LLM：第一次调用工具，第二次返回答案
        llm_config = LLMConfig(provider="mock", model="test")
        llm = MockProvider(config=llm_config)

        # 第一次响应：调用工具
        llm.add_response(
            LLMResponse(
                model="test",
                content="I need to read the file.",
                finish_reason="tool_calls",
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="read_file",
                        arguments_json=json.dumps({"path": "test.txt"}),
                    )
                ],
            )
        )

        # 第二次响应：返回答案
        llm.add_response(
            LLMResponse(
                model="test",
                content="The file contains: Hello World",
                finish_reason="stop",
                tool_calls=[],
            )
        )

        # 创建 Agent Loop
        loop = AgentLoop(
            llm=llm,
            registry=registry,
            store=store,
            repo_root=str(repo_path),
            config=AgentLoopConfig(),
        )

        # 执行
        result = loop.run(user_goal="Read test.txt and tell me what it says")

        # 验证
        assert result.success is True
        assert result.iterations == 2
        assert "Hello World" in result.final_message
        assert result.error is None


def test_agent_loop_max_iterations():
    """测试：达到最大迭代次数"""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        db_path = Path(":memory:")

        ws = RepoWorkspace.from_path(str(repo_path))
        registry = ToolRegistry()
        store = SQLiteStore(db_path=db_path)
        store.init_schema()

        # Mock LLM：一直返回工具调用（无限循环）
        llm_config = LLMConfig(provider="mock", model="test")
        llm = MockProvider(config=llm_config)

        # 设置一个会无限循环的响应
        for _ in range(10):
            llm.add_response(
                LLMResponse(
                    model="test",
                    content="Calling tool again...",
                    finish_reason="tool_calls",
                    tool_calls=[
                        ToolCall(
                            id=f"call_{_}",
                            name="unknown_tool",
                            arguments_json="{}",
                        )
                    ],
                )
            )

        # 创建 Agent Loop（最大 5 次迭代）
        loop = AgentLoop(
            llm=llm,
            registry=registry,
            store=store,
            repo_root=str(repo_path),
            config=AgentLoopConfig(max_iterations=5),
        )

        # 执行
        result = loop.run(user_goal="Test max iterations")

        # 验证
        assert result.success is False
        assert result.iterations == 5
        assert "max iterations" in result.error.lower()


def test_agent_loop_tool_error():
    """测试：工具执行失败"""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        db_path = Path(":memory:")

        ws = RepoWorkspace.from_path(str(repo_path))
        registry = ToolRegistry()

        # 注册一个会失败的工具
        from codinggirl.core.contracts import ToolCall as ContractToolCall
        from codinggirl.core.contracts import ToolResult

        def failing_handler(call: ContractToolCall) -> ToolResult:
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                ok=False,
                error="Tool failed intentionally",
            )

        registry.register(
            ToolSpec(
                name="failing_tool",
                description="A tool that always fails",
                input_schema={"type": "object", "properties": {}},
            ),
            failing_handler,
        )

        store = SQLiteStore(db_path=db_path)
        store.init_schema()

        # Mock LLM
        llm_config = LLMConfig(provider="mock", model="test")
        llm = MockProvider(config=llm_config)

        # 第一次：调用失败的工具
        llm.add_response(
            LLMResponse(
                model="test",
                content="Calling tool...",
                finish_reason="tool_calls",
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="failing_tool",
                        arguments_json="{}",
                    )
                ],
            )
        )

        # 第二次：处理错误并返回
        llm.add_response(
            LLMResponse(
                model="test",
                content="The tool failed, but I handled it gracefully.",
                finish_reason="stop",
                tool_calls=[],
            )
        )

        # 创建 Agent Loop
        loop = AgentLoop(
            llm=llm,
            registry=registry,
            store=store,
            repo_root=str(repo_path),
            config=AgentLoopConfig(),
        )

        # 执行
        result = loop.run(user_goal="Test tool error handling")

        # 验证：即使工具失败，loop 也能继续
        assert result.success is True
        assert result.iterations == 2
        assert "handled it gracefully" in result.final_message
