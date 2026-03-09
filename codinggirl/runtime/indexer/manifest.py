from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from codinggirl.runtime.workspace import RepoWorkspace


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _guess_lang(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".js": "javascript",
        ".jsx": "jsx",
        ".md": "markdown",
        ".json": "json",
        ".yml": "yaml",
        ".yaml": "yaml",
    }.get(ext, "text")


def _is_ignored(rel: str) -> bool:
    parts = rel.split("/")
    ignored_dirs = {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        "tmp",
        ".codinggirl",
    }
    if any(p in ignored_dirs for p in parts):
        return True
    ignored_suffix = {".pyc", ".pyo", ".log", ".sqlite3"}
    return any(rel.endswith(s) for s in ignored_suffix)


@dataclass(frozen=True, slots=True)
class ManifestEntry:
    path: str
    lang: str
    size: int
    mtime: float
    sha256: str

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "lang": self.lang,
            "size": self.size,
            "mtime": self.mtime,
            "sha256": self.sha256,
        }


def load_manifest(path: Path) -> dict[str, ManifestEntry]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    entries: dict[str, ManifestEntry] = {}
    for item in data.get("entries", []):
        e = ManifestEntry(
            path=item["path"],
            lang=item["lang"],
            size=int(item["size"]),
            mtime=float(item["mtime"]),
            sha256=item["sha256"],
        )
        entries[e.path] = e
    return entries


def save_manifest(path: Path, entries: dict[str, ManifestEntry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "entries": [entries[k].to_dict() for k in sorted(entries.keys())],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def scan_manifest(
    workspace: RepoWorkspace,
    *,
    previous: dict[str, ManifestEntry] | None = None,
    max_file_size: int = 1_000_000,
) -> tuple[dict[str, ManifestEntry], list[str], list[str], list[str]]:
    """Return (entries, added, changed, removed)."""
    prev = previous or {}
    entries: dict[str, ManifestEntry] = {}

    for p in workspace.root.rglob("*"):
        if not p.is_file():
            continue
        rel = str(p.relative_to(workspace.root)).replace("\\", "/")
        if _is_ignored(rel):
            continue
        stat = p.stat()
        if stat.st_size > max_file_size:
            continue
        lang = _guess_lang(p)

        prev_e = prev.get(rel)
        if prev_e and prev_e.mtime == stat.st_mtime and prev_e.size == stat.st_size:
            entries[rel] = prev_e
            continue

        entries[rel] = ManifestEntry(
            path=rel,
            lang=lang,
            size=stat.st_size,
            mtime=stat.st_mtime,
            sha256=_file_sha256(p),
        )

    old_keys = set(prev.keys())
    new_keys = set(entries.keys())
    added = sorted(new_keys - old_keys)
    removed = sorted(old_keys - new_keys)
    changed = sorted(
        k for k in (new_keys & old_keys) if entries[k].sha256 != prev[k].sha256
    )
    return entries, added, changed, removed
