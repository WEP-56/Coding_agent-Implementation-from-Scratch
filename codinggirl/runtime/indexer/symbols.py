from __future__ import annotations

import ast
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from codinggirl.runtime.workspace import RepoWorkspace


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS symbol (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  path TEXT NOT NULL,
  name TEXT NOT NULL,
  kind TEXT NOT NULL,
  line_start INTEGER NOT NULL,
  line_end INTEGER,
  signature TEXT,
  UNIQUE(path, name, kind, line_start)
);

CREATE TABLE IF NOT EXISTS import_edge (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  path TEXT NOT NULL,
  module TEXT NOT NULL,
  line INTEGER NOT NULL,
  UNIQUE(path, module, line)
);

CREATE INDEX IF NOT EXISTS idx_symbol_path ON symbol(path);
CREATE INDEX IF NOT EXISTS idx_symbol_name ON symbol(name);
CREATE INDEX IF NOT EXISTS idx_import_path ON import_edge(path);
"""


@dataclass(frozen=True, slots=True)
class SymbolRecord:
    path: str
    name: str
    kind: str
    line_start: int
    line_end: int | None
    signature: str | None


@dataclass(frozen=True, slots=True)
class ImportRecord:
    path: str
    module: str
    line: int


def _func_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = [a.arg for a in node.args.args]
    if node.args.vararg:
        args.append("*" + node.args.vararg.arg)
    if node.args.kwarg:
        args.append("**" + node.args.kwarg.arg)
    return f"{node.name}({', '.join(args)})"


def extract_python_symbols(path: str, text: str) -> tuple[list[SymbolRecord], list[ImportRecord]]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return [], []

    symbols: list[SymbolRecord] = []
    imports: list[ImportRecord] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            symbols.append(
                SymbolRecord(
                    path=path,
                    name=node.name,
                    kind="class",
                    line_start=node.lineno,
                    line_end=getattr(node, "end_lineno", None),
                    signature=node.name,
                )
            )
        elif isinstance(node, ast.FunctionDef):
            symbols.append(
                SymbolRecord(
                    path=path,
                    name=node.name,
                    kind="function",
                    line_start=node.lineno,
                    line_end=getattr(node, "end_lineno", None),
                    signature=_func_signature(node),
                )
            )
        elif isinstance(node, ast.AsyncFunctionDef):
            symbols.append(
                SymbolRecord(
                    path=path,
                    name=node.name,
                    kind="async_function",
                    line_start=node.lineno,
                    line_end=getattr(node, "end_lineno", None),
                    signature=_func_signature(node),
                )
            )
        elif isinstance(node, ast.Import):
            for n in node.names:
                imports.append(ImportRecord(path=path, module=n.name, line=node.lineno))
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            imports.append(ImportRecord(path=path, module=mod, line=node.lineno))

    return symbols, imports


_TS_FUNC_RE = re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(")
_TS_CLASS_RE = re.compile(r"^\s*(?:export\s+)?(?:default\s+)?class\s+([A-Za-z_$][\w$]*)\b")
_TS_VAR_RE = re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\b")
_TS_TYPELIKE_RE = re.compile(r"^\s*export\s+(interface|type|enum)\s+([A-Za-z_$][\w$]*)\b")
_TS_IMPORT_FROM_RE = re.compile(r"^\s*import\s+.+?\s+from\s+['\"]([^'\"]+)['\"]")
_TS_IMPORT_BARE_RE = re.compile(r"^\s*import\s+['\"]([^'\"]+)['\"]")
_TS_REQUIRE_RE = re.compile(r"require\(\s*['\"]([^'\"]+)['\"]\s*\)")


def extract_ts_js_symbols(path: str, text: str) -> tuple[list[SymbolRecord], list[ImportRecord]]:
    symbols: list[SymbolRecord] = []
    imports: list[ImportRecord] = []
    for i, line in enumerate(text.splitlines(), start=1):
        m = _TS_TYPELIKE_RE.match(line)
        if m:
            kind, name = m.group(1), m.group(2)
            symbols.append(
                SymbolRecord(
                    path=path,
                    name=name,
                    kind=kind,
                    line_start=i,
                    line_end=None,
                    signature=name,
                )
            )

        m = _TS_CLASS_RE.match(line)
        if m:
            name = m.group(1)
            symbols.append(
                SymbolRecord(
                    path=path,
                    name=name,
                    kind="class",
                    line_start=i,
                    line_end=None,
                    signature=name,
                )
            )

        m = _TS_FUNC_RE.match(line)
        if m:
            name = m.group(1)
            signature = name
            if "(" in line and ")" in line:
                sig = line.strip()
                signature = sig[:200]
            symbols.append(
                SymbolRecord(
                    path=path,
                    name=name,
                    kind="function",
                    line_start=i,
                    line_end=None,
                    signature=signature,
                )
            )

        m = _TS_VAR_RE.match(line)
        if m:
            name = m.group(1)
            symbols.append(
                SymbolRecord(
                    path=path,
                    name=name,
                    kind="variable",
                    line_start=i,
                    line_end=None,
                    signature=name,
                )
            )

        m = _TS_IMPORT_FROM_RE.match(line)
        if m:
            imports.append(ImportRecord(path=path, module=m.group(1), line=i))
        m = _TS_IMPORT_BARE_RE.match(line)
        if m:
            imports.append(ImportRecord(path=path, module=m.group(1), line=i))
        for req in _TS_REQUIRE_RE.findall(line):
            imports.append(ImportRecord(path=path, module=req, line=i))

    return symbols, imports


def open_symbols_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    return conn


def upsert_file_symbols(
    conn: sqlite3.Connection,
    *,
    path: str,
    symbols: list[SymbolRecord],
    imports: list[ImportRecord],
) -> None:
    cur = conn.cursor()
    cur.execute("DELETE FROM symbol WHERE path=?", (path,))
    cur.execute("DELETE FROM import_edge WHERE path=?", (path,))
    cur.executemany(
        "INSERT INTO symbol(path,name,kind,line_start,line_end,signature) VALUES (?,?,?,?,?,?)",
        [(s.path, s.name, s.kind, s.line_start, s.line_end, s.signature) for s in symbols],
    )
    cur.executemany(
        "INSERT INTO import_edge(path,module,line) VALUES (?,?,?)",
        [(i.path, i.module, i.line) for i in imports],
    )
    conn.commit()


def delete_file_symbols(conn: sqlite3.Connection, path: str) -> None:
    cur = conn.cursor()
    cur.execute("DELETE FROM symbol WHERE path=?", (path,))
    cur.execute("DELETE FROM import_edge WHERE path=?", (path,))
    conn.commit()


def index_changed_python_files(
    workspace: RepoWorkspace,
    *,
    conn: sqlite3.Connection,
    changed_files: list[str],
    removed_files: list[str],
) -> None:
    index_changed_source_files(
        workspace,
        conn=conn,
        changed_files=changed_files,
        removed_files=removed_files,
    )


def index_changed_source_files(
    workspace: RepoWorkspace,
    *,
    conn: sqlite3.Connection,
    changed_files: list[str],
    removed_files: list[str],
    max_bytes: int = 1_000_000,
) -> None:
    for rel in removed_files:
        delete_file_symbols(conn, rel)
    for rel in changed_files:
        low = rel.lower()
        if low.endswith(".py"):
            text = workspace.read_text(rel, max_bytes=max_bytes)
            syms, imps = extract_python_symbols(rel, text)
            upsert_file_symbols(conn, path=rel, symbols=syms, imports=imps)
            continue
        if low.endswith((".ts", ".tsx", ".js", ".jsx")):
            text = workspace.read_text(rel, max_bytes=max_bytes)
            syms, imps = extract_ts_js_symbols(rel, text)
            upsert_file_symbols(conn, path=rel, symbols=syms, imports=imps)
