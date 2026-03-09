from __future__ import annotations

from pathlib import Path

from codinggirl.runtime.indexer.manifest import load_manifest, save_manifest, scan_manifest
from codinggirl.runtime.indexer.repo_map import build_repo_map_items, render_repo_map
from codinggirl.runtime.indexer.symbols import index_changed_python_files, open_symbols_db
from codinggirl.runtime.workspace import RepoWorkspace


def test_manifest_incremental_scan(tmp_path: Path):
    ws = RepoWorkspace.from_path(tmp_path)
    ws.write_text("a.py", "def foo():\n    return 1\n")

    m_path = ws.resolve_path(".codinggirl/index/manifest.json")
    prev = load_manifest(m_path)
    entries, added, changed, removed = scan_manifest(ws, previous=prev)
    assert "a.py" in added
    assert changed == []
    assert removed == []

    save_manifest(m_path, entries)
    prev2 = load_manifest(m_path)
    ws.write_text("a.py", "def foo():\n    return 2\n")
    entries2, added2, changed2, removed2 = scan_manifest(ws, previous=prev2)
    assert added2 == []
    assert "a.py" in changed2
    assert removed2 == []


def test_symbols_and_repo_map_generation(tmp_path: Path):
    ws = RepoWorkspace.from_path(tmp_path)
    ws.write_text(
        "pkg/mod.py",
        "import os\n\nclass A:\n    pass\n\ndef hello(name):\n    return name\n",
    )

    conn = open_symbols_db(ws.resolve_path(".codinggirl/index/symbols.sqlite"))
    try:
        index_changed_python_files(
            ws,
            conn=conn,
            changed_files=["pkg/mod.py"],
            removed_files=[],
        )
        rows = conn.execute("SELECT name, kind FROM symbol WHERE path='pkg/mod.py'").fetchall()
        names = {(r[0], r[1]) for r in rows}
        assert ("A", "class") in names
        assert ("hello", "function") in names

        items = build_repo_map_items(conn)
        text = render_repo_map(items, max_lines=50)
        assert "pkg/mod.py" in text
        assert "hello" in text
    finally:
        conn.close()


def test_removed_file_clears_symbols(tmp_path: Path):
    ws = RepoWorkspace.from_path(tmp_path)
    ws.write_text("x.py", "def x():\n    return 1\n")

    db = ws.resolve_path(".codinggirl/index/symbols.sqlite")
    conn = open_symbols_db(db)
    try:
        index_changed_python_files(ws, conn=conn, changed_files=["x.py"], removed_files=[])
        c1 = conn.execute("SELECT COUNT(*) FROM symbol WHERE path='x.py'").fetchone()[0]
        assert c1 > 0

        ws.resolve_path("x.py").unlink()
        index_changed_python_files(ws, conn=conn, changed_files=[], removed_files=["x.py"])
        c2 = conn.execute("SELECT COUNT(*) FROM symbol WHERE path='x.py'").fetchone()[0]
        assert c2 == 0
    finally:
        conn.close()


def test_repo_map_focus_terms_boost(tmp_path: Path):
    ws = RepoWorkspace.from_path(tmp_path)
    ws.write_text("auth/login.py", "def signInUser(name):\n    return name\n")
    ws.write_text("misc/util.py", "def helper():\n    return 1\n")

    conn = open_symbols_db(ws.resolve_path(".codinggirl/index/symbols.sqlite"))
    try:
        index_changed_python_files(
            ws,
            conn=conn,
            changed_files=["auth/login.py", "misc/util.py"],
            removed_files=[],
        )
        items = build_repo_map_items(conn, focus_terms={"auth", "login", "signinuser"})
        assert len(items) >= 2
        # focused auth symbol should be ranked on top or near top
        top_paths = [x.path for x in items[:2]]
        assert "auth/login.py" in top_paths
    finally:
        conn.close()
