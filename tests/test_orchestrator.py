from __future__ import annotations

from pathlib import Path

from codinggirl.core.orchestrator import execute_goal


def test_orchestrator_success_replace(tmp_path: Path):
    (tmp_path / "notes.txt").write_text("hello old world\n", encoding="utf-8")
    res = execute_goal(
        repo_root=str(tmp_path),
        goal="replace [old] with [new] in [notes.txt]",
        db_path=".codinggirl/test.sqlite3",
    )
    assert res.status == "DONE"
    assert "new" in (tmp_path / "notes.txt").read_text(encoding="utf-8")


def test_orchestrator_unsupported_goal_aborts(tmp_path: Path):
    (tmp_path / "notes.txt").write_text("hello\n", encoding="utf-8")
    res = execute_goal(
        repo_root=str(tmp_path),
        goal="please refactor everything",
        db_path=".codinggirl/test.sqlite3",
    )
    assert res.status == "ABORTED"
