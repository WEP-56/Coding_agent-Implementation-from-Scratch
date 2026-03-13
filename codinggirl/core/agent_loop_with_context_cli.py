"""
Agent Loop with Context Management CLI - 测试入口

用法：
    py -m codinggirl.core.agent_loop_with_context_cli --goal "你的任务" --provider openai --model gpt-4
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from codinggirl.core.agent_loop_with_context import (
    AgentLoopWithContext,
    AgentLoopWithContextConfig,
)
from codinggirl.core.contracts import Plan, PlanStep
from codinggirl.runtime.defaults import create_default_registry
from codinggirl.runtime.llm_adapter.factory import create_llm_provider
from codinggirl.runtime.llm_adapter.models import LLMConfig
from codinggirl.runtime.storage_sqlite import SQLiteStore
from codinggirl.runtime.workspace import RepoWorkspace


def build_system_prompt(repo_root: str) -> str:
    """构建系统提示词"""
    return f"""You are a coding agent working in repository: {repo_root}

You have access to the following tools:
- fs_read_file: Read file contents
- fs_write_file: Write/create files
- fs_replace_text: Replace text in files
- fs_insert_at_line: Insert text at specific line
- fs_list_files: List files in directory
- fs_glob: Find files by pattern
- search_rg: Search text in files
- patch_apply_unified_diff: Apply unified diff patches
- index_build: Build code index
- index_query_repo_map: Query repository structure
- index_query_imports: Query import relationships
- cmd_run: Run shell commands
- todo_update: Update task progress (IMPORTANT: use this to track your work!)

Guidelines:
1. Break complex tasks into steps
2. Use todo_update to mark tasks as in_progress or completed
3. Always read files before editing them
4. Use specific tools instead of bash when possible
5. Verify changes after making them
6. Explain your reasoning

Work step by step to accomplish the user's goal."""


def generate_plan_from_goal(goal: str) -> Plan:
    """从用户目标生成简单的计划"""
    steps = []

    if any(word in goal.lower() for word in ["read", "find", "search", "list", "count", "analyze"]):
        steps.append(PlanStep(
            step_id="s1",
            title="Locate and read files",
            description="Find and read the target files",
        ))

    if any(word in goal.lower() for word in ["analyze", "understand", "check", "count"]):
        steps.append(PlanStep(
            step_id="s2",
            title="Analyze content",
            description="Analyze the file content or structure",
        ))

    if any(word in goal.lower() for word in ["write", "create", "modify", "update", "change"]):
        steps.append(PlanStep(
            step_id="s3",
            title="Make changes",
            description="Apply the required changes",
        ))
        steps.append(PlanStep(
            step_id="s4",
            title="Verify changes",
            description="Verify the changes were applied correctly",
        ))

    if any(word in goal.lower() for word in ["report", "summarize", "tell", "count"]):
        steps.append(PlanStep(
            step_id=f"s{len(steps)+1}",
            title="Report results",
            description="Provide the final answer or summary",
        ))

    if not steps:
        steps = [
            PlanStep(step_id="s1", title="Understand the task", description="Analyze what needs to be done"),
            PlanStep(step_id="s2", title="Execute the task", description="Perform the required actions"),
            PlanStep(step_id="s3", title="Report results", description="Provide the final answer"),
        ]

    return Plan(task_id="user_task", steps=steps)


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent Loop with Context Management CLI")
    parser.add_argument("--goal", required=True, help="User goal/task")
    parser.add_argument("--repo", default=".", help="Repository root path")
    parser.add_argument("--provider", default="openai", help="LLM provider (openai/anthropic)")
    parser.add_argument("--model", default="gpt-4", help="Model name")
    parser.add_argument("--base-url", help="API base URL (optional)")
    parser.add_argument("--api-key", help="API key (optional, can use env var)")
    parser.add_argument("--db", default=".codinggirl/agent_loop_context.sqlite3", help="Database path")
    parser.add_argument("--max-iterations", type=int, default=50, help="Max loop iterations")
    parser.add_argument("--temperature", type=float, default=0.0, help="LLM temperature")
    parser.add_argument("--permission", default="write", choices=["readonly", "write", "exec"], help="Permission mode")
    parser.add_argument("--no-todo", action="store_true", help="Disable todo tracking")
    parser.add_argument("--no-context", action="store_true", help="Disable context management")
    parser.add_argument("--keep-recent", type=int, default=3, help="Micro-compact: keep recent N results")
    parser.add_argument("--token-threshold", type=int, default=50000, help="Auto-compact: token threshold")

    args = parser.parse_args()

    # 初始化
    repo_root = Path(args.repo).resolve()
    if not repo_root.exists():
        print(f"Error: Repository not found: {repo_root}", file=sys.stderr)
        return 1

    print(f"Repository: {repo_root}")
    print(f"Goal: {args.goal}")
    print(f"Provider: {args.provider} / {args.model}")
    print(f"Permission: {args.permission}")
    print(f"Todo tracking: {'disabled' if args.no_todo else 'enabled'}")
    print(f"Context management: {'disabled' if args.no_context else 'enabled'}")
    if not args.no_context:
        print(f"  - Micro-compact: keep recent {args.keep_recent} results")
        print(f"  - Auto-compact: threshold {args.token_threshold} tokens")
    print("-" * 60)

    # 创建组件
    ws = RepoWorkspace.from_path(str(repo_root))
    registry = create_default_registry(ws)

    db_path = repo_root / args.db
    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = SQLiteStore(db_path=db_path)
    store.init_schema()

    llm_config = LLMConfig(
        provider=args.provider,
        model=args.model,
        base_url=args.base_url,
        api_key=args.api_key,
    )
    llm = create_llm_provider(llm_config)

    loop_config = AgentLoopWithContextConfig(
        max_iterations=args.max_iterations,
        temperature=args.temperature,
        system_prompt=build_system_prompt(str(repo_root)),
        enable_todo=not args.no_todo,
        enable_context_management=not args.no_context,
        keep_recent_results=args.keep_recent,
        token_threshold=args.token_threshold,
    )

    agent_loop = AgentLoopWithContext(
        llm=llm,
        registry=registry,
        store=store,
        repo_root=str(repo_root),
        config=loop_config,
    )

    # 生成初始计划
    plan = generate_plan_from_goal(args.goal) if not args.no_todo else None

    if plan:
        print("\n[*] Generated plan:")
        for step in plan.steps:
            print(f"  - {step.title}: {step.description}")
        print()

    # 执行
    print("[*] Starting agent loop with context management...\n")
    result = agent_loop.run(
        user_goal=args.goal,
        permission_mode=args.permission,
        initial_plan=plan,
    )

    # 输出结果
    print("\n" + "=" * 60)
    print(f"Run ID: {result.run_id}")
    print(f"Success: {result.success}")
    print(f"Iterations: {result.iterations}")

    if result.todo_stats:
        print(f"Todo stats: {result.todo_stats}")

    if result.context_stats:
        print(f"Context stats: {result.context_stats}")

    if result.error:
        print(f"Error: {result.error}")
        return 1

    print(f"\nFinal message:\n{result.final_message}")
    print("\n[+] Agent loop completed successfully!")

    # 从数据库读取压缩事件统计
    try:
        import json
        conn = store.connect()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT kind, payload_json FROM event WHERE run_id = ? AND kind IN (?, ?)",
            (result.run_id, "context_micro_compact", "context_auto_compact")
        )

        micro_compacts = []
        auto_compacts = []

        for row in cursor.fetchall():
            kind = row[0]
            payload = json.loads(row[1])
            if kind == "context_micro_compact":
                micro_compacts.append(payload)
            elif kind == "context_auto_compact":
                auto_compacts.append(payload)

        if micro_compacts or auto_compacts:
            print("\n[*] Context compression summary:")
            print(f"  - Micro-compacts: {len(micro_compacts)}")
            print(f"  - Auto-compacts: {len(auto_compacts)}")

            if micro_compacts:
                total_saved = sum(e.get("saved_tokens", 0) for e in micro_compacts)
                print(f"  - Total tokens saved (micro): ~{total_saved}")

            if auto_compacts:
                total_saved = sum(e.get("saved_tokens", 0) for e in auto_compacts)
                print(f"  - Total tokens saved (auto): ~{total_saved}")
    except Exception as e:
        print(f"\n[!] Could not read compression stats: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
