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
    assert isinstance(res.content, dict)
    assert isinstance((res.content or {}).get("conflict"), dict)
    assert ws.read_text("a.txt") == "one\ntwo\n"


def test_patch_apply_preserves_crlf(tmp_path: Path):
    ws = RepoWorkspace.from_path(tmp_path)
    p = tmp_path / "a.txt"
    p.write_bytes(b"one\r\ntwo\r\n")

    patch = """--- a/a.txt
+++ b/a.txt
@@ -1,2 +1,2 @@
 one
-two
+TWO
"""

    reg = create_default_registry(ws)
    store = SQLiteStore(tmp_path / "db.sqlite3")
    store.init_schema()
    run_id = uuid.uuid4().hex
    store.create_run(run_id, created_at=utc_now_iso(), metadata={})
    runner = ToolRunner(registry=reg, store=store, run_id=run_id)

    res = runner.call("patch_apply_unified_diff", {"patch": patch})
    assert res.ok is True
    data = p.read_bytes()
    assert b"\r\n" in data
    assert b"\n" not in data.replace(b"\r\n", b"")


def test_patch_apply_dry_run_does_not_modify_or_backup(tmp_path: Path):
    ws = RepoWorkspace.from_path(tmp_path)
    ws.write_text("a.txt", "one\ntwo\n")

    patch = """--- a/a.txt
+++ b/a.txt
@@ -1,2 +1,2 @@
 one
-two
+TWO
"""

    reg = create_default_registry(ws)
    store = SQLiteStore(tmp_path / "db.sqlite3")
    store.init_schema()
    run_id = uuid.uuid4().hex
    store.create_run(run_id, created_at=utc_now_iso(), metadata={})
    runner = ToolRunner(registry=reg, store=store, run_id=run_id)

    res = runner.call("patch_apply_unified_diff", {"patch": patch, "dry_run": True, "backup": True})
    assert res.ok is True
    assert ws.read_text("a.txt") == "one\ntwo\n"
    assert (tmp_path / ".codinggirl" / "backups").exists() is False


def test_patch_apply_conflict_does_not_create_backup(tmp_path: Path):
    ws = RepoWorkspace.from_path(tmp_path)
    ws.write_text("a.txt", "one\ntwo\n")
    ws.write_text("b.txt", "alpha\nbeta\n")

    patch = """--- a/a.txt
+++ b/a.txt
@@ -1,2 +1,2 @@
 one
-two
+TWO
--- a/b.txt
+++ b/b.txt
@@ -1,2 +1,2 @@
 alpha
-BETA
+beta
"""

    reg = create_default_registry(ws)
    store = SQLiteStore(tmp_path / "db.sqlite3")
    store.init_schema()
    run_id = uuid.uuid4().hex
    store.create_run(run_id, created_at=utc_now_iso(), metadata={})
    runner = ToolRunner(registry=reg, store=store, run_id=run_id)

    res = runner.call("patch_apply_unified_diff", {"patch": patch, "backup": True, "backup_dir": ".codinggirl/backups"})
    assert res.ok is False
    assert ws.read_text("a.txt") == "one\ntwo\n"
    assert ws.read_text("b.txt") == "alpha\nbeta\n"
    assert (tmp_path / ".codinggirl" / "backups").exists() is False
