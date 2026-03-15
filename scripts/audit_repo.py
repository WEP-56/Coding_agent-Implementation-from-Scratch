from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(r"E:\coding agent")

SKIP_DIRS = {
    ".git",
    "node_modules",
    "target",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "tmp",
}

SCAN_EXTS = {".py", ".rs", ".ts", ".tsx", ".md"}

MARKERS = ("TODO", "FIXME", "HACK")


def should_skip(p: Path) -> bool:
    return any(part in SKIP_DIRS for part in p.parts)


@dataclass
class Finding:
    kind: str
    file: str
    line: int | None
    text: str
    meta: dict


def iter_files() -> Iterable[Path]:
    for p in ROOT.rglob("*"):
        if p.is_dir():
            continue
        if should_skip(p):
            continue
        if p.suffix.lower() not in SCAN_EXTS:
            continue
        yield p


def read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def add_marker_findings(findings: list[Finding]) -> None:
    for p in iter_files():
        text = read_text(p)
        if not text:
            continue
        if not any(m in text for m in MARKERS):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for m in MARKERS:
                if m in line:
                    findings.append(
                        Finding(
                            kind=f"MARKER:{m}",
                            file=str(p.relative_to(ROOT)).replace("\\", "/"),
                            line=i,
                            text=line.strip()[:260],
                            meta={},
                        )
                    )


KIND_RE = re.compile(r"\bkind\s*=\s*\"([^\"]+)\"")


def extract_python_event_kinds() -> dict[str, int]:
    """Best-effort: scan for store.append_event(kind="...") occurrences."""
    counts: dict[str, int] = {}
    for p in ROOT.rglob("codinggirl/**/*.py"):
        if p.is_dir() or should_skip(p):
            continue
        text = read_text(p)
        for m in KIND_RE.finditer(text):
            k = m.group(1)
            counts[k] = counts.get(k, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def extract_event_types_constants() -> set[str]:
    p = ROOT / "codinggirl/core/event_types.py"
    text = read_text(p)
    vals = set(re.findall(r"=\s*\"([^\"]+)\"", text))
    # filter to only event-type looking strings
    return {v for v in vals if ":" in v}


def main() -> int:
    findings: list[Finding] = []

    add_marker_findings(findings)

    python_kinds = extract_python_event_kinds()
    event_types = extract_event_types_constants()

    # Heuristic mismatches
    if event_types:
        # Our runtime uses underscore kinds; event_types uses colon kinds.
        if any("_" in k for k in python_kinds.keys()) and any(":" in e for e in event_types):
            findings.append(
                Finding(
                    kind="ARCH:EVENT_SEMANTICS_DIVERGED",
                    file="codinggirl/core/event_types.py",
                    line=None,
                    text=(
                        "event_types.py defines colon-style event types (context:stats_update), "
                        "but runtime persistence/desktop stream uses underscore kinds (context_stats_update)."
                    ),
                    meta={
                        "event_types_sample": sorted(list(event_types))[:10],
                        "python_kinds_sample": list(python_kinds.keys())[:10],
                    },
                )
            )

    out = {
        "root": str(ROOT),
        "markerCount": sum(1 for f in findings if f.kind.startswith("MARKER:")),
        "findingCount": len(findings),
        "pythonEventKindsTop": list(python_kinds.items())[:50],
        "eventTypesConstants": sorted(list(event_types))[:60],
        "findings": [
            {
                "kind": f.kind,
                "file": f.file,
                "line": f.line,
                "text": f.text,
                "meta": f.meta,
            }
            for f in findings
        ],
    }

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
