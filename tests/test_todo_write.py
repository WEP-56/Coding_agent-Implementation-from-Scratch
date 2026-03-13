"""
测试 TodoWrite 机制
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from codinggirl.core.agent_loop_with_todo import AgentLoopWithTodo, AgentLoopWithTodoConfig
from codinggirl.core.contracts import Plan, PlanStep
from codinggirl.runtime.llm_adapter.models import LLMConfig, LLMResponse, ToolCall
from codinggirl.runtime.llm_adapter.mock_provider import MockProvider
from codinggirl.runtime.storage_sqlite import SQLiteStore
from codinggirl.runtime.tools.registry import ToolRegistry
from codinggirl.runtime.workspace import RepoWorkspace


def test_agent_loop_with_todo():
    """测试：Agent Loop 使用 TodoWrite 追踪任务进度"""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        db_path = Path(":memory:")

        # 创建组件
        ws = RepoWorkspace.from_path(str(repo_path))
        registry = ToolRegistry()
        store = SQLiteStore(db_path=db_path)
        store.init_schema()

        # 创建一个简单的 Plan
        plan = Plan(
            task_id="test_task",
            steps=[
                PlanStep(step_id="s1", title="Read file", description="Read the target file"),
                PlanStep(step_id="s2", title="Analyze content", description="Analyze file content"),
                PlanStep(step_id="s3", title="Report findings", description="Report the findings"),
            ],
        )

        # Mock LLM：模拟 agent 使用 todo_update 工具
        llm_config = LLMConfig(provider="mock", model="test")
        llm = MockProvider(config=llm_config)

        # 第 1 轮：开始第一个任务
        llm.add_response(
            LLMResponse(
                model="test",
                content="Starting task 1",
                finish_reason="tool_calls",
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="todo_update",
                        arguments_json=json.dumps({"updates": [{"step_id": "s1", "status": "in_progress"}]}),
                    )
                ],
            )
        )

        # 第 2 轮：完成第一个任务，开始第二个
        llm.add_response(
            LLMResponse(
                model="test",
                content="Moving to task 2",
                finish_reason="tool_calls",
                tool_calls=[
                    ToolCall(
                        id="call_2",
                        name="todo_update",
                        arguments_json=json.dumps(
                            {"updates": [{"step_id": "s1", "status": "completed"}, {"step_id": "s2", "status": "in_progress"}]}
                        ),
                    )
                ],
            )
        )

        # 第 3 轮：完成所有任务
        llm.add_response(
            LLMResponse(
                model="test",
                content="All tasks completed!",
                finish_reason="stop",
                tool_calls=[],
            )
        )

        # 创建 Agent Loop with Todo
        loop = AgentLoopWithTodo(
            llm=llm,
            registry=registry,
            store=store,
            repo_root=str(repo_path),
            config=AgentLoopWithTodoConfig(enable_todo=True),
        )

        # 执行
        result = loop.run(user_goal="Complete the tasks", initial_plan=plan)

        # 验证
        assert result.success is True
        assert result.iterations == 3
        assert result.todo_stats is not None
        assert result.todo_stats["completed"] >= 1  # 至少完成了一个任务
        print(f"[+] Todo stats: {result.todo_stats}")


if __name__ == "__main__":
    test_agent_loop_with_todo()
    print("\n[+] TodoWrite test passed!")
