from __future__ import annotations

import uuid
from pathlib import Path

from codinggirl.core.contracts import utc_now_iso
from codinggirl.runtime.defaults import create_default_registry
from codinggirl.runtime.storage_sqlite import SQLiteStore
from codinggirl.runtime.tools.runner import ToolRunner
from codinggirl.runtime.workspace import RepoWorkspace


def test_patch_apply_success_and_backup(tmp_path: Path):
    ws = RepoWorkspace.from_path(tmp_path)
    ws.write_text("a.txt", "one\ntwo\n")

    patch = """--- a/a.txt
+++ b/a.txt
@@ -1,2 +1,3 @@
 one
-two
+TWO
+three
"""

    reg = create_default_registry(ws)
    store = SQLiteStore(tmp_path / "db.sqlite3")
    store.init_schema()
    run_id = uuid.uuid4().hex
    store.create_run(run_id, created_at=utc_now_iso(), metadata={})
    runner = ToolRunner(registry=reg, store=store, run_id=run_id)

    res = runner.call("patch_apply_unified_diff", {"patch": patch, "backup": True, "backup_dir": ".codinggirl/backups"})
    assert res.ok is True
    assert ws.read_text("a.txt") == "one\nTWO\nthree\n"
    backups = ws.list_dir(".codinggirl/backups")
    assert any(x.endswith(".bak") for x in backups)


def test_patch_apply_conflict_does_not_modify(tmp_path: Path):
    ws = RepoWorkspace.from_path(tmp_path)
    ws.write_text("a.txt", "one\ntwo\n")

    bad_patch = """--- a/a.txt
+++ b/a.txt
@@ -1,2 +1,2 @@
 one
-TWO
+two
"""

    reg = create_default_registry(ws)
    store = SQLiteStore(tmp_path / "db.sqlite3")
    store.init_schema()
    run_id = uuid.uuid4().hex
    store.create_run(run_id, created_at=utc_now_iso(), metadata={})
    runner = ToolRunner(registry=reg, store=store, run_id=run_id)

    res = runner.call("patch_apply_unified_diff", {"patch": bad_patch})
    assert res.ok is False
    assert ws.read_text("a.txt") == "one\ntwo\n"
