"""
Agent Loop CLI - 测试入口

用法：
    py -m codinggirl.core.agent_loop_cli --goal "你的任务" --provider openai --model gpt-4
    py -m codinggirl.core.agent_loop_cli --goal "你的任务" --provider anthropic --model claude-3-5-sonnet-20241022
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from codinggirl.core.agent_loop import AgentLoop, AgentLoopConfig
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

Guidelines:
1. Always read files before editing them
2. Use specific tools (fs_replace_text) instead of bash when possible
3. Verify changes after making them
4. Break complex tasks into steps
5. Explain your reasoning

Work step by step to accomplish the user's goal."""


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent Loop CLI")
    parser.add_argument("--goal", required=True, help="User goal/task")
    parser.add_argument("--repo", default=".", help="Repository root path")
    parser.add_argument("--provider", default="openai", help="LLM provider (openai/anthropic)")
    parser.add_argument("--model", default="gpt-4", help="Model name")
    parser.add_argument("--base-url", help="API base URL (optional)")
    parser.add_argument("--api-key", help="API key (optional, can use env var)")
    parser.add_argument("--db", default=".codinggirl/agent_loop.sqlite3", help="Database path")
    parser.add_argument("--max-iterations", type=int, default=50, help="Max loop iterations")
    parser.add_argument("--temperature", type=float, default=0.0, help="LLM temperature")
    parser.add_argument("--permission", default="write", choices=["readonly", "write", "exec"], help="Permission mode")

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

    loop_config = AgentLoopConfig(
        max_iterations=args.max_iterations,
        temperature=args.temperature,
        system_prompt=build_system_prompt(str(repo_root)),
    )

    agent_loop = AgentLoop(
        llm=llm,
        registry=registry,
        store=store,
        repo_root=str(repo_root),
        config=loop_config,
    )

    # 执行
    print("\n[*] Starting agent loop...\n")
    result = agent_loop.run(
        user_goal=args.goal,
        permission_mode=args.permission,
    )

    # 输出结果
    print("\n" + "=" * 60)
    print(f"Run ID: {result.run_id}")
    print(f"Success: {result.success}")
    print(f"Iterations: {result.iterations}")

    if result.error:
        print(f"Error: {result.error}")
        return 1

    print(f"\nFinal message:\n{result.final_message}")
    print("\n[+] Agent loop completed successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
