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
