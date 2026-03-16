"""
Enhanced Agent Loop CLI - 测试增强版 agent loop

使用示例：
python -m codinggirl.core.agent_loop_enhanced_cli "帮我优化这个项目的性能"
"""
from __future__ import annotations

import os
import sys

from codinggirl.core.agent_loop_enhanced import EnhancedAgentLoop, EnhancedAgentLoopConfig
from codinggirl.core.contracts import Plan, PlanStep
from codinggirl.runtime.llm_adapter.factory import create_llm_provider
from codinggirl.runtime.llm_adapter.models import LLMConfig
from codinggirl.runtime.storage_sqlite import SQLiteStore
from codinggirl.runtime.tools.builtins_cmd import register_cmd_tools
from codinggirl.runtime.tools.builtins_fs import register_fs_tools
from codinggirl.runtime.tools.builtins_search import register_search_tools
from codinggirl.runtime.tools.registry import ToolRegistry


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("Usage: python -m codinggirl.core.agent_loop_enhanced_cli <goal>")
        sys.exit(1)

    user_goal = sys.argv[1]
    repo_root = os.getcwd()

    # 配置 LLM
    llm_config = LLMConfig(
        provider="openai_compatible",
        model=os.environ.get("CODINGGIRL_MODEL", "gpt-4"),
        base_url=os.environ.get("CODINGGIRL_BASE_URL"),
        api_key=os.environ.get("CODINGGIRL_API_KEY"),
        timeout_sec=120,
    )

    llm = create_llm_provider(llm_config)

    # 初始化工具注册表
    registry = ToolRegistry()
    register_fs_tools(registry, repo_root)
    register_search_tools(registry, repo_root)
    register_cmd_tools(registry, repo_root)

    # 初始化存储
    db_path = os.path.join(repo_root, ".codinggirl", "runs.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    store = SQLiteStore(db_path)

    # 创建一个简单的计划（可选）
    initial_plan = Plan(
        goal=user_goal,
        steps=[
            PlanStep(
                step_id="s1",
                title="Understand the codebase",
                description="Read key files and understand the project structure",
            ),
            PlanStep(
                step_id="s2",
                title="Identify optimization opportunities",
                description="Find performance bottlenecks and areas for improvement",
            ),
            PlanStep(
                step_id="s3",
                title="Implement optimizations",
                description="Apply the identified optimizations",
            ),
            PlanStep(
                step_id="s4",
                title="Verify improvements",
                description="Test and verify the optimizations work correctly",
            ),
        ],
    )

    # 配置增强版 agent loop
    config = EnhancedAgentLoopConfig(
        max_iterations=50,
        temperature=0.0,
        system_prompt="""You are a helpful coding assistant.

Your task is to help the user with their coding goals.

Guidelines:
- Read files before modifying them
- Make targeted, minimal changes
- Verify your changes work correctly
- Use the todo_update tool to track your progress
""",
        enable_todo=True,
        enable_context_management=True,
        enable_loop_guards=True,
        enable_parallel_execution=True,
        context_window_size=15,
        context_max_tokens=100000,
    )

    # 创建 agent loop
    loop = EnhancedAgentLoop(
        llm=llm,
        registry=registry,
        store=store,
        repo_root=repo_root,
        config=config,
    )

    # 运行
    print(f"🚀 Starting enhanced agent loop...")
    print(f"📝 Goal: {user_goal}")
    print(f"📁 Repo: {repo_root}")
    print()

    result = loop.run(
        user_goal=user_goal,
        permission_mode="write",
        initial_plan=initial_plan,
        task_phase="exploration",
    )

    # 输出结果
    print("\n" + "=" * 80)
    print("📊 Results")
    print("=" * 80)
    print(f"✅ Success: {result.success}")
    print(f"🔄 Iterations: {result.iterations}")

    if result.todo_stats:
        print(f"\n📋 Todo Stats:")
        print(f"  - Total: {result.todo_stats['total']}")
        print(f"  - Completed: {result.todo_stats['completed']}")
        print(f"  - In Progress: {result.todo_stats['in_progress']}")
        print(f"  - Pending: {result.todo_stats['pending']}")

    if result.context_stats:
        print(f"\n💾 Context Stats:")
        print(f"  - Compressions: {result.context_stats['compression_count']}")
        print(f"  - Tokens Saved: {result.context_stats['total_tokens_saved']}")
        print(f"  - Avg Compression Ratio: {result.context_stats['avg_compression_ratio']:.2f}")

    if result.loop_guard_stats:
        print(f"\n🛡️ Loop Guard Stats:")
        print(f"  - Total Tool Calls: {result.loop_guard_stats['total_tool_calls']}")
        print(f"  - Consecutive Identical: {result.loop_guard_stats['consecutive_identical']}")

    if result.performance_stats:
        print(f"\n⚡ Performance Stats:")
        print(f"  - Total Time: {result.performance_stats['total_time_s']:.2f}s")
        print(f"  - LLM Time: {result.performance_stats['llm_time_s']:.2f}s")
        print(f"  - Tool Time: {result.performance_stats['tool_time_s']:.2f}s")
        print(f"  - Avg Iteration: {result.performance_stats['avg_iteration_time_s']:.2f}s")

    if result.error:
        print(f"\n❌ Error: {result.error}")

    print(f"\n💬 Final Message:")
    print(result.final_message)

    print(f"\n📝 Run ID: {result.run_id}")
    print(f"💾 Database: {db_path}")


if __name__ == "__main__":
    main()
