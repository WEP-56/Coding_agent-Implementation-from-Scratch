"""
Desktop Agent Stream CLI

Purpose:
  Run the Python agent loop and stream structured events as JSONL on stdout.
  This is designed to be launched by the Tauri backend and consumed by the desktop UI.

Output protocol (one JSON object per line):
  - {"type":"run_started", ...}
  - {"type":"event", "runId": "...", "kind": "...", "ts": "...", "payload": {...}}
  - {"type":"run_finished", ...}

Notes:
  - Do not print any non-JSON output.
  - All fields are best-effort and kept stable for UI consumption.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from codinggirl.core.agent_loop_with_subagent import (
    AgentLoopWithSubagent,
    AgentLoopWithSubagentConfig,
)
from codinggirl.core.contracts import Plan, PlanStep
from codinggirl.core.policy import PermissionMode
from codinggirl.runtime.defaults import create_default_registry
from codinggirl.runtime.llm_adapter.factory import create_llm_provider
from codinggirl.runtime.llm_adapter.models import LLMConfig
from codinggirl.runtime.storage_sqlite import SQLiteStore
from codinggirl.runtime.workspace import RepoWorkspace


def _emit(obj: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


class StreamingSQLiteStore:
    def __init__(self, inner: SQLiteStore) -> None:
        self._inner = inner

    # Delegate connect/init/create_run as-is, but stream create_run metadata.
    def connect(self):  # noqa: ANN001
        return self._inner.connect()

    def init_schema(self) -> None:
        self._inner.init_schema()

    def create_run(
        self,
        run_id: str,
        *,
        created_at: str,
        status: str = "running",
        parent_run_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._inner.create_run(
            run_id,
            created_at=created_at,
            status=status,
            parent_run_id=parent_run_id,
            metadata=metadata,
        )
        _emit(
            {
                "type": "run_started",
                "runId": run_id,
                "createdAt": created_at,
                "status": status,
                "parentRunId": parent_run_id,
                "metadata": metadata or {},
            }
        )

    def append_event(
        self,
        *,
        run_id: str,
        kind: str,
        ts: str,
        payload: dict[str, Any],
        step_id: str | None = None,
    ) -> None:
        self._inner.append_event(run_id=run_id, kind=kind, ts=ts, payload=payload, step_id=step_id)
        _emit(
            {
                "type": "event",
                "runId": run_id,
                "kind": kind,
                "ts": ts,
                "stepId": step_id,
                "payload": payload,
            }
        )

    # Delegate tool call recording + replay helpers
    def record_tool_call_start(self, **kwargs: Any) -> None:  # noqa: ANN401
        self._inner.record_tool_call_start(**kwargs)
        _emit(
            {
                "type": "tool_call_started",
                "callId": kwargs.get("call_id"),
                "runId": kwargs.get("run_id"),
                "stepId": kwargs.get("step_id"),
                "toolName": kwargs.get("tool_name"),
                "createdAt": kwargs.get("created_at"),
                "input": kwargs.get("input_payload"),
            }
        )

    def record_tool_call_finish(self, **kwargs: Any) -> None:  # noqa: ANN401
        self._inner.record_tool_call_finish(**kwargs)
        _emit(
            {
                "type": "tool_call_finished",
                "callId": kwargs.get("call_id"),
                "completedAt": kwargs.get("completed_at"),
                "ok": kwargs.get("ok"),
                "output": kwargs.get("output_payload"),
                "error": kwargs.get("error_payload"),
            }
        )

    def get_tool_call_output(self, call_id: str):  # noqa: ANN001
        return self._inner.get_tool_call_output(call_id)

    def get_tool_call_record(self, call_id: str):  # noqa: ANN001
        return self._inner.get_tool_call_record(call_id)


def _build_system_prompt(repo_root: str) -> str:
    return (
        "You are a coding agent working in repository: "
        + repo_root
        + "\n\n"
        + "Work step by step. Use tools when needed. Keep edits minimal and verifiable.\n"
        + "When asked to review/summarize code, DO NOT loop on generic browsing. Prefer targeted tools:\n"
        + "- Use fs_glob / fs_list_files to find entrypoints\n"
        + "- Use search_rg to find API calls or networking layers\n"
        + "- Use fs_read_many_files / fs_read_range to read the most relevant files\n"
        + "Then produce a written summary.\n"
        + "IMPORTANT: For any repo-related task (read/search/summarize/edit), you MUST call at least one repo tool before answering.\n"
        + "If a task is multi-step, keep progress updated via todo_update.\n"
    )


def _generate_plan_from_goal(goal: str) -> Plan:
    steps: list[PlanStep] = [
        PlanStep(step_id="s1", title="Explore", description="Locate relevant files and context"),
        PlanStep(step_id="s2", title="Implement", description="Make the necessary changes"),
        PlanStep(step_id="s3", title="Verify", description="Verify behavior and report results"),
    ]
    if any(word in goal.lower() for word in ["read", "find", "search", "list", "count", "analyze"]):
        steps[1] = PlanStep(step_id="s2", title="Analyze", description="Analyze the repository and the target area")
        steps[2] = PlanStep(step_id="s3", title="Report", description="Report results and next actions")
    return Plan(task_id="desktop", steps=steps)


def main() -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--goal", required=True)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--provider", default="openai-compatible")
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--db", default=".codinggirl/desktop_agent.sqlite3")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--max-iterations", type=int, default=400)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--permission", default="write", choices=["readonly", "write", "exec"])
    parser.add_argument("--no-todo", action="store_true")
    parser.add_argument("--no-context", action="store_true")
    parser.add_argument("--no-subagent", action="store_true")
    parser.add_argument("--keep-recent", type=int, default=8)
    parser.add_argument("--token-threshold", type=int, default=50000)
    args = parser.parse_args()

    repo_root = Path(args.repo).resolve()
    if not repo_root.exists():
        _emit({"type": "run_finished", "success": False, "error": f"repo not found: {repo_root}"})
        return 2

    ws = RepoWorkspace.from_path(str(repo_root))
    registry = create_default_registry(ws)

    db_path = repo_root / str(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    inner_store = SQLiteStore(db_path=db_path)
    inner_store.init_schema()
    store = StreamingSQLiteStore(inner_store)

    llm_cfg = LLMConfig(
        provider=str(args.provider),
        model=str(args.model),
        base_url=str(args.base_url) if str(args.base_url).strip() else None,
        api_key=str(args.api_key) if str(args.api_key).strip() else None,
        timeout_sec=60,
    )
    llm = create_llm_provider(llm_cfg)

    run_id = str(args.run_id).strip() or None
    permission_mode: PermissionMode = args.permission  # type: ignore[assignment]

    loop_cfg = AgentLoopWithSubagentConfig(
        max_iterations=int(args.max_iterations),
        temperature=float(args.temperature),
        system_prompt=_build_system_prompt(str(repo_root)),
        enable_todo=not bool(args.no_todo),
        enable_context_management=not bool(args.no_context),
        enable_subagent=not bool(args.no_subagent),
        keep_recent_results=int(args.keep_recent),
        token_threshold=int(args.token_threshold),
    )
    agent = AgentLoopWithSubagent(
        llm=llm,
        registry=registry,
        store=store,  # type: ignore[arg-type]
        repo_root=str(repo_root),
        config=loop_cfg,
    )

    plan = _generate_plan_from_goal(str(args.goal)) if not args.no_todo else None

    result = agent.run(
        user_goal=str(args.goal),
        permission_mode=permission_mode,
        run_id=run_id,
        initial_plan=plan,
    )

    _emit(
        {
            "type": "run_finished",
            "runId": result.run_id,
            "success": bool(result.success),
            "iterations": int(result.iterations),
            "finalMessage": str(result.final_message),
            "todoStats": result.todo_stats,
            "contextStats": result.context_stats,
            "subagentStats": result.subagent_stats,
            "error": result.error,
        }
    )
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
