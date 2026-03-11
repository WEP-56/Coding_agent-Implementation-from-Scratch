from __future__ import annotations

from pathlib import Path

import pytest

from codinggirl.runtime.workspace import RepoWorkspace, WorkspaceError


def test_workspace_denies_absolute_path(tmp_path: Path):
    ws = RepoWorkspace.from_path(tmp_path)
    with pytest.raises(WorkspaceError):
        ws.resolve_path(str(tmp_path / "x.txt"))


def test_workspace_denies_escape(tmp_path: Path):
    ws = RepoWorkspace.from_path(tmp_path)
    with pytest.raises(WorkspaceError):
        ws.resolve_path("../escape.txt")


def test_workspace_read_write_roundtrip(tmp_path: Path):
    ws = RepoWorkspace.from_path(tmp_path)
    ws.write_text("a/b.txt", "hello\n")
    assert ws.read_text("a/b.txt").startswith("hello")
    assert "b.txt" in "".join(ws.list_dir("a"))


def test_workspace_read_text_size_limit(tmp_path: Path):
    ws = RepoWorkspace.from_path(tmp_path)
    ws.write_text("big.txt", "x" * 20)
    with pytest.raises(WorkspaceError):
        ws.read_text("big.txt", max_bytes=10)


def test_workspace_read_text_range_allows_large_files(tmp_path: Path):
    ws = RepoWorkspace.from_path(tmp_path)
    ws.write_text("big.txt", "0123456789\n" * 60_000)
    with pytest.raises(WorkspaceError):
        ws.read_text("big.txt")

    r = ws.read_text_range("big.txt", start_line=10, limit=3)
    assert r["start_line"] == 10
    assert r["end_line"] == 12
    assert r["total_lines"] == 60_000
    assert r["truncated"] is True
    assert "0123456789" in str(r["text"])


def test_workspace_preserves_crlf_on_write(tmp_path: Path):
    ws = RepoWorkspace.from_path(tmp_path)
    p = tmp_path / "crlf.txt"
    p.write_bytes(b"one\r\ntwo\r\n")

    ws.replace_text("crlf.txt", old_text="two", new_text="TWO")
    data = p.read_bytes()
    assert b"\r\n" in data
    assert b"\n" not in data.replace(b"\r\n", b"")


def test_workspace_insert_preserves_crlf(tmp_path: Path):
    ws = RepoWorkspace.from_path(tmp_path)
    p = tmp_path / "crlf.txt"
    p.write_bytes(b"one\r\ntwo\r\n")

    ws.insert_text_at_line("crlf.txt", line=2, text="INSERT\n")
    data = p.read_bytes()
    assert b"\r\n" in data
    assert b"\n" not in data.replace(b"\r\n", b"")
