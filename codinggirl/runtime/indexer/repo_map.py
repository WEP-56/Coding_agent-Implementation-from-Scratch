from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from math import sqrt
@dataclass(frozen=True, slots=True)
class RepoMapItem:
    path: str
    name: str
    kind: str
    line_start: int
    line_end: int | None
    signature: str | None
    score: int


def _fetch_import_counts(conn: sqlite3.Connection) -> dict[str, int]:
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT path, COUNT(*) AS c FROM import_edge GROUP BY path"
    ).fetchall()
    return {str(r[0]): int(r[1]) for r in rows}


def _fetch_symbol_name_counts(conn: sqlite3.Connection) -> dict[str, int]:
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT name, COUNT(*) AS c FROM symbol GROUP BY name"
    ).fetchall()
    return {str(r[0]): int(r[1]) for r in rows}


def _is_structured_identifier(name: str) -> bool:
    # snake_case / kebab-case / camelCase or PascalCase
    return (
        "_" in name
        or "-" in name
        or bool(re.search(r"[a-z][A-Z]", name))
        or bool(re.search(r"[A-Z][a-z]", name))
    )


def _path_components(path: str) -> set[str]:
    return {p.lower() for p in re.split(r"[/.\\_-]+", path) if p}


def _is_important_file(path: str) -> bool:
    low = path.lower()
    important_names = {
        "readme.md",
        "pyproject.toml",
        "setup.py",
        "main.py",
        "requirements.txt",
        "package.json",
    }
    if any(low.endswith("/" + name) or low == name for name in important_names):
        return True
    if "__init__.py" in low:
        return True
    return False


def build_repo_map_items(
    conn: sqlite3.Connection,
    *,
    focus_terms: set[str] | None = None,
) -> list[RepoMapItem]:
    import_counts = _fetch_import_counts(conn)
    name_counts = _fetch_symbol_name_counts(conn)
    focus = {x.strip().lower() for x in (focus_terms or set()) if x.strip()}
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT path,name,kind,line_start,line_end,signature FROM symbol"
    ).fetchall()

    items: list[RepoMapItem] = []
    for r in rows:
        path = str(r[0])
        name = str(r[1])
        kind = str(r[2])
        line_start = int(r[3])
        line_end = r[4] if r[4] is None else int(r[4])
        signature = r[5] if r[5] is None else str(r[5])

        score = 0.0
        # lightweight ranking heuristics:
        # - import centrality with sqrt dampening
        # - identifier frequency
        # - structured identifier bonus / private penalty
        # - focus-term path and symbol boosts
        # - important files bonus
        score += sqrt(import_counts.get(path, 0)) * 6
        score += name_counts.get(name, 0) * 2

        if _is_structured_identifier(name) and len(name) >= 8:
            score += 8
        if name.startswith("_"):
            score -= 4

        if kind == "class":
            score += 5
        if "__init__" in path or path.endswith("main.py"):
            score += 4

        if _is_important_file(path):
            score += 12

        if focus:
            path_terms = _path_components(path)
            if path_terms & focus:
                score += 20
            if name.lower() in focus:
                score += 20

        items.append(
            RepoMapItem(
                path=path,
                name=name,
                kind=kind,
                line_start=line_start,
                line_end=line_end,
                signature=signature,
                score=int(round(score)),
            )
        )

    items.sort(key=lambda x: (-x.score, x.path, x.line_start))
    return items


def query_repo_map_items(
    conn: sqlite3.Connection,
    *,
    focus_terms: set[str] | None = None,
    path_query: str | None = None,
    name_query: str | None = None,
    kinds: list[str] | None = None,
    include_tests: bool = False,
    max_results: int = 200,
) -> list[RepoMapItem]:
    import_counts = _fetch_import_counts(conn)
    name_counts = _fetch_symbol_name_counts(conn)
    focus = {x.strip().lower() for x in (focus_terms or set()) if x.strip()}
    cur = conn.cursor()

    clauses: list[str] = []
    params: list[object] = []
    if not include_tests:
        clauses.append("path NOT LIKE 'tests/%'")
    if path_query:
        clauses.append("path LIKE ?")
        params.append(f"%{path_query}%")
    if name_query:
        clauses.append("name LIKE ?")
        params.append(f"%{name_query}%")
    if kinds:
        placeholders = ",".join("?" for _ in kinds)
        clauses.append(f"kind IN ({placeholders})")
        params.extend(kinds)

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT path,name,kind,line_start,line_end,signature FROM symbol{where}"
    rows = cur.execute(sql, params).fetchall()

    def score_item(path: str, name: str, kind: str) -> int:
        score = 0.0
        score += sqrt(import_counts.get(path, 0)) * 6
        score += name_counts.get(name, 0) * 2
        if _is_structured_identifier(name) and len(name) >= 8:
            score += 8
        if name.startswith("_"):
            score -= 4
        if kind == "class":
            score += 5
        if "__init__" in path or path.endswith("main.py"):
            score += 4
        if _is_important_file(path):
            score += 12
        if focus:
            path_terms = _path_components(path)
            if path_terms & focus:
                score += 20
            if name.lower() in focus:
                score += 20
        return int(round(score))

    items: list[RepoMapItem] = []
    for r in rows:
        path = str(r[0])
        name = str(r[1])
        kind = str(r[2])
        line_start = int(r[3])
        line_end = r[4] if r[4] is None else int(r[4])
        signature = r[5] if r[5] is None else str(r[5])
        items.append(
            RepoMapItem(
                path=path,
                name=name,
                kind=kind,
                line_start=line_start,
                line_end=line_end,
                signature=signature,
                score=score_item(path, name, kind),
            )
        )

    items.sort(key=lambda x: (-x.score, x.path, x.line_start))
    if max_results > 0:
        return items[:max_results]
    return items


def render_repo_map(items: list[RepoMapItem], *, max_lines: int = 300) -> str:
    out: list[str] = []
    out.append("# Repo Map")
    out.append("")
    out.append("# format: path:line kind name signature [score]")
    out.append("")

    count = 0
    for it in items:
        if it.path.startswith("tests/"):
            continue
        sig = it.signature or it.name
        out.append(f"{it.path}:{it.line_start} {it.kind} {it.name} {sig} [score={it.score}]")
        count += 1
        if count >= max_lines:
            break

    out.append("")
    out.append(f"# total_shown={min(len(items), max_lines)} total_items={len(items)}")
    return "\n".join(out) + "\n"
