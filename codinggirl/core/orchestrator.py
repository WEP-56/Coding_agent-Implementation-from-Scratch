from __future__ import annotations

from pathlib import Path
import uuid
from dataclasses import dataclass

from codinggirl.core.coder import make_unified_diff_for_replace, parse_replace_goal
from codinggirl.core.contracts import Task, utc_now_iso
from codinggirl.core.policy import PermissionPolicy
from codinggirl.core.planner import build_plan
from codinggirl.core.reviewer import review_patch
from codinggirl.core.state_machine import RunState
from codinggirl.runtime.defaults import create_default_registry
from codinggirl.runtime.storage_sqlite import SQLiteStore
from codinggirl.runtime.tools.runner import ToolRunner
from codinggirl.runtime.workspace import RepoWorkspace


@dataclass(frozen=True, slots=True)
class OrchestratorResult:
    run_id: str
    status: str
    message: str


def execute_goal(*, repo_root: str, goal: str, db_path: str) -> OrchestratorResult:
    run_id = uuid.uuid4().hex
    state = RunState(run_id=run_id)

    # normalize db path relative to repo root if not absolute
    dbp = Path(db_path)
    if not dbp.is_absolute():
        dbp = Path(repo_root) / dbp
    store = SQLiteStore(db_path=dbp)
    store.init_schema()
    store.create_run(run_id, created_at=utc_now_iso(), metadata={"goal": goal, "repo_root": repo_root})

    ws = RepoWorkspace.from_path(repo_root)
    registry = create_default_registry(ws)

    task = Task(task_id=run_id, goal=goal, repo_root=repo_root, mode="write", adapter="cli")
    runner = ToolRunner(registry=registry, store=store, run_id=run_id, permission=PermissionPolicy(mode=task.mode))

    try:
        state.transition("PLANNED")
        plan = build_plan(task)
        store.append_event(run_id=run_id, kind="planned", ts=utc_now_iso(), payload={"steps": len(plan.steps)})

        ins = parse_replace_goal(goal)
        read_res = runner.call("fs_read_file", {"path": ins.file})
        if not read_res.ok:
            state.transition("PATCH_FAILED")
            store.append_event(run_id=run_id, kind="patch_failed", ts=utc_now_iso(), payload={"reason": read_res.error})
            state.transition("ABORTED")
            return OrchestratorResult(run_id=run_id, status=state.status, message=read_res.error or "read failed")

        before_text = str((read_res.content or {}).get("text", ""))
        patch = make_unified_diff_for_replace(path=ins.file, before_text=before_text, old=ins.old, new=ins.new)

        rv = review_patch(patch)
        if not rv.ok:
            state.transition("PATCH_FAILED")
            store.append_event(run_id=run_id, kind="patch_review_failed", ts=utc_now_iso(), payload={"reasons": rv.reasons})
            state.transition("ABORTED")
            return OrchestratorResult(run_id=run_id, status=state.status, message="; ".join(rv.reasons))

        state.transition("PATCHED")
        store.append_event(run_id=run_id, kind="patched", ts=utc_now_iso(), payload={"risk": rv.risk_level})

        apply_res = runner.call("patch_apply_unified_diff", {"patch": patch, "backup": True})
        if not apply_res.ok:
            state.transition("PATCH_FAILED")
            store.append_event(run_id=run_id, kind="patch_apply_failed", ts=utc_now_iso(), payload={"reason": apply_res.error})
            state.transition("ABORTED")
            return OrchestratorResult(run_id=run_id, status=state.status, message=apply_res.error or "patch apply failed")

        state.transition("VERIFIED")
        verify = runner.call("fs_read_file", {"path": ins.file})
        if not verify.ok:
            state.transition("VERIFY_FAILED")
            store.append_event(run_id=run_id, kind="verify_failed", ts=utc_now_iso(), payload={"reason": verify.error})
            state.transition("ABORTED")
            return OrchestratorResult(run_id=run_id, status=state.status, message=verify.error or "verify read failed")

        text_now = str((verify.content or {}).get("text", ""))
        if ins.new not in text_now:
            state.transition("VERIFY_FAILED")
            store.append_event(run_id=run_id, kind="verify_failed", ts=utc_now_iso(), payload={"reason": "new text not found"})
            state.transition("ABORTED")
            return OrchestratorResult(run_id=run_id, status=state.status, message="verification failed: new text not found")

        state.transition("APPLIED")
        store.append_event(run_id=run_id, kind="applied", ts=utc_now_iso(), payload={"file": ins.file})
        state.transition("DONE")
        store.append_event(run_id=run_id, kind="done", ts=utc_now_iso(), payload={"status": "ok"})
        return OrchestratorResult(run_id=run_id, status=state.status, message="done")

    except ValueError as e:
        # includes parse failures and invalid transitions
        if state.status not in {"ABORTED", "DONE"}:
            try:
                state.transition("ABORTED")
            except ValueError:
                pass
        store.append_event(run_id=run_id, kind="aborted", ts=utc_now_iso(), payload={"reason": str(e)})
        return OrchestratorResult(run_id=run_id, status=state.status, message=str(e))
