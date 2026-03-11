from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ModuleSpec:
    root: str
    exts: tuple[str, ...]
    exclude_dir_names: tuple[str, ...] = (
        ".git",
        ".codinggirl",
        "node_modules",
        "dist",
        "tmp",
        "__pycache__",
        ".pytest_cache",
    )


def _iter_code_files(root: Path, *, exts: tuple[str, ...], exclude_dir_names: tuple[str, ...]) -> list[Path]:
    files: list[Path] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in exts:
            continue
        if any(part in exclude_dir_names for part in p.parts):
            continue
        files.append(p)
    files.sort(key=lambda x: str(x).lower())
    return files


def _count_lines(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8", errors="replace", newline=None) as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent

    modules = [
        ModuleSpec(root="codinggirl", exts=(".py",)),
        ModuleSpec(root="tests", exts=(".py",)),
        ModuleSpec(root="apps/desktop/src", exts=(".ts", ".tsx", ".js", ".jsx")),
        ModuleSpec(root="apps/desktop/src-tauri/src", exts=(".rs",)),
        ModuleSpec(root="docs", exts=(".md", ".html")),
    ]

    rows: list[tuple[str, int, int]] = []
    for m in modules:
        root_path = repo_root / m.root
        if not root_path.exists():
            rows.append((m.root, 0, 0))
            continue
        files = _iter_code_files(root_path, exts=m.exts, exclude_dir_names=m.exclude_dir_names)
        lines = sum(_count_lines(p) for p in files)
        rows.append((m.root, len(files), lines))

    root_w = max(len("root"), *(len(r[0]) for r in rows))
    files_w = max(len("files"), *(len(str(r[1])) for r in rows))
    lines_w = max(len("lines"), *(len(str(r[2])) for r in rows))

    print(f"{'root'.ljust(root_w)} {'files'.rjust(files_w)} {'lines'.rjust(lines_w)}")
    for root, files, lines in rows:
        print(f"{root.ljust(root_w)} {str(files).rjust(files_w)} {str(lines).rjust(lines_w)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

