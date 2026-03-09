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
