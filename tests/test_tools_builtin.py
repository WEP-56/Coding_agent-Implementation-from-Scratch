from __future__ import annotations

import uuid
from pathlib import Path

from codinggirl.core.contracts import utc_now_iso
from codinggirl.runtime.defaults import create_default_registry
from codinggirl.runtime.storage_sqlite import SQLiteStore
from codinggirl.runtime.tools.runner import ToolRunner
from codinggirl.runtime.workspace import RepoWorkspace


def test_toolrunner_fs_read_and_search(tmp_path: Path):
    ws = RepoWorkspace.from_path(tmp_path)
    ws.write_text("hello.txt", "hello world\n")

    reg = create_default_registry(ws)
    store = SQLiteStore(tmp_path / "db.sqlite3")
    store.init_schema()
    run_id = uuid.uuid4().hex
    store.create_run(run_id, created_at=utc_now_iso(), metadata={})

    runner = ToolRunner(registry=reg, store=store, run_id=run_id)
    r1 = runner.call("fs_read_file", {"path": "hello.txt"})
    assert r1.ok is True
    assert "hello world" in (r1.content or {}).get("text", "")

    r2 = runner.call("search_rg", {"pattern": "hello"})
    assert r2.ok is True
    results = (r2.content or {}).get("results", [])
    assert any(x.get("path") == "hello.txt" for x in results)


def test_toolrunner_rejects_invalid_args(tmp_path: Path):
    ws = RepoWorkspace.from_path(tmp_path)
    ws.write_text("hello.txt", "hello world\n")

    reg = create_default_registry(ws)
    store = SQLiteStore(tmp_path / "db.sqlite3")
    store.init_schema()
    run_id = uuid.uuid4().hex
    store.create_run(run_id, created_at=utc_now_iso(), metadata={})

    runner = ToolRunner(registry=reg, store=store, run_id=run_id)

    missing_required = runner.call("fs_read_file", {})
    assert missing_required.ok is False
    assert "invalid args" in (missing_required.error or "")

    unexpected_prop = runner.call("fs_read_file", {"path": "hello.txt", "nope": 1})
    assert unexpected_prop.ok is False
    assert "invalid args" in (unexpected_prop.error or "")


def test_toolrunner_fs_write_and_insert(tmp_path: Path):
    ws = RepoWorkspace.from_path(tmp_path)
    reg = create_default_registry(ws)
    store = SQLiteStore(tmp_path / "db.sqlite3")
    store.init_schema()
    run_id = uuid.uuid4().hex
    store.create_run(run_id, created_at=utc_now_iso(), metadata={})

    runner = ToolRunner(registry=reg, store=store, run_id=run_id)
    w1 = runner.call("fs_write_file", {"path": "a.txt", "text": "one\ntwo\n"})
    assert w1.ok is True
    assert ws.read_text("a.txt") == "one\ntwo\n"

    i1 = runner.call("fs_insert_at_line", {"path": "a.txt", "line": 2, "text": "INSERT\n"})
    assert i1.ok is True
    assert ws.read_text("a.txt") == "one\nINSERT\ntwo\n"


def test_toolrunner_fs_read_many_files(tmp_path: Path):
    ws = RepoWorkspace.from_path(tmp_path)
    ws.write_text("a.txt", "one\ntwo\nthree\n")
    ws.write_text("b.txt", "alpha\nbeta\ngamma\n")
    ws.write_text("big.txt", "0123456789\n" * 60_000)

    reg = create_default_registry(ws)
    store = SQLiteStore(tmp_path / "db.sqlite3")
    store.init_schema()
    run_id = uuid.uuid4().hex
    store.create_run(run_id, created_at=utc_now_iso(), metadata={})
    runner = ToolRunner(registry=reg, store=store, run_id=run_id)

    res = runner.call(
        "fs_read_many_files",
        {
            "items": [
                {"path": "a.txt", "start_line": 2, "limit": 2},
                {"path": "b.txt"},
                {"path": "big.txt", "start_line": 10, "limit": 3},
                {"path": "missing.txt"},
            ],
            "max_total_bytes": 200_000,
        },
    )
    assert res.ok is True
    payload = res.content or {}
    items = payload.get("items", [])
    assert isinstance(items, list)
    assert items[0]["path"] == "a.txt"
    assert items[0]["start_line"] == 2
    assert "two" in str(items[0]["text"])
    assert items[1]["path"] == "b.txt"
    assert "alpha" in str(items[1]["text"])
    assert items[2]["path"] == "big.txt"
    assert items[2]["total_lines"] == 60_000
    assert items[3]["path"] == "missing.txt"
    assert items[3]["ok"] is False


def test_toolrunner_fs_list_files(tmp_path: Path):
    ws = RepoWorkspace.from_path(tmp_path)
    ws.write_text("a/a.txt", "one\n")
    ws.write_text("a/b.txt", "two\n")
    ws.write_text("b/c.txt", "three\n")

    reg = create_default_registry(ws)
    store = SQLiteStore(tmp_path / "db.sqlite3")
    store.init_schema()
    run_id = uuid.uuid4().hex
    store.create_run(run_id, created_at=utc_now_iso(), metadata={})
    runner = ToolRunner(registry=reg, store=store, run_id=run_id)

    res = runner.call("fs_list_files", {"path": ".", "recursive": True, "ignore": ["**/b/**"]})
    assert res.ok is True
    items = (res.content or {}).get("items", [])
    paths = {x.get("path") for x in items}
    assert "a/a.txt" in paths
    assert "a/b.txt" in paths
    assert "b/c.txt" not in paths


def test_toolrunner_fs_glob_supports_ignore(tmp_path: Path):
    ws = RepoWorkspace.from_path(tmp_path)
    ws.write_text("a/a.txt", "one\n")
    ws.write_text("b/b.txt", "two\n")

    reg = create_default_registry(ws)
    store = SQLiteStore(tmp_path / "db.sqlite3")
    store.init_schema()
    run_id = uuid.uuid4().hex
    store.create_run(run_id, created_at=utc_now_iso(), metadata={})
    runner = ToolRunner(registry=reg, store=store, run_id=run_id)

    res = runner.call("fs_glob", {"pattern": "**/*.txt", "ignore": ["b/**"]})
    assert res.ok is True
    items = (res.content or {}).get("items", [])
    paths = {x.get("path") for x in items}
    assert "a/a.txt" in paths
    assert "b/b.txt" not in paths
