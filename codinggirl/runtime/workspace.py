from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class WorkspaceError(RuntimeError):
    pass


def _is_within_root(root: Path, target: Path) -> bool:
    try:
        target.relative_to(root)
        return True
    except ValueError:
        return False


@dataclass(frozen=True, slots=True)
class RepoWorkspace:
    root: Path

    @staticmethod
    def from_path(path: str | Path) -> "RepoWorkspace":
        root = Path(path).expanduser().resolve(strict=False)
        return RepoWorkspace(root=root)

    def resolve_path(self, rel_path: str) -> Path:
        # Normalize separators and disallow absolute paths early
        p = Path(rel_path)
        if p.is_absolute():
            raise WorkspaceError(f"absolute path not allowed: {rel_path}")
        resolved = (self.root / p).resolve(strict=False)
        if not _is_within_root(self.root, resolved):
            raise WorkspaceError(f"path escapes workspace root: {rel_path}")
        return resolved

    def read_text(self, rel_path: str, *, max_bytes: int = 512_000) -> str:
        p = self.resolve_path(rel_path)
        if not p.exists() or not p.is_file():
            raise WorkspaceError(f"file not found: {rel_path}")
        size = p.stat().st_size
        if size > max_bytes:
            raise WorkspaceError(f"file too large ({size} bytes): {rel_path}")
        return p.read_text(encoding="utf-8", errors="replace")

    def write_text(self, rel_path: str, content: str) -> None:
        p = self.resolve_path(rel_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8", newline="\n")

    def list_dir(self, rel_path: str = ".") -> list[str]:
        p = self.resolve_path(rel_path)
        if not p.exists() or not p.is_dir():
            raise WorkspaceError(f"dir not found: {rel_path}")
        out: list[str] = []
        for child in sorted(p.iterdir(), key=lambda x: x.name.lower()):
            suffix = "/" if child.is_dir() else ""
            out.append(child.name + suffix)
        return out
