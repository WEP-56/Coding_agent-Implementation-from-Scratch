from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS run (
  run_id TEXT PRIMARY KEY,
  parent_run_id TEXT,
  created_at TEXT NOT NULL,
  status TEXT NOT NULL,
  metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS step (
  step_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  name TEXT NOT NULL,
  status TEXT NOT NULL,
  inputs_json TEXT,
  outputs_json TEXT,
  started_at TEXT,
  completed_at TEXT,
  error_json TEXT
);

CREATE TABLE IF NOT EXISTS tool_call (
  call_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  step_id TEXT,
  tool_name TEXT NOT NULL,
  input_json TEXT NOT NULL,
  output_json TEXT,
  status TEXT NOT NULL,
  error_json TEXT,
  created_at TEXT NOT NULL,
  completed_at TEXT
);

CREATE TABLE IF NOT EXISTS event (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  step_id TEXT,
  kind TEXT NOT NULL,
  ts TEXT NOT NULL,
  payload_json TEXT
);
"""


@dataclass(frozen=True, slots=True)
class SQLiteStore:
    db_path: Path

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)

    def create_run(
        self,
        run_id: str,
        *,
        created_at: str,
        status: str = "running",
        parent_run_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO run(run_id,parent_run_id,created_at,status,metadata_json) VALUES (?,?,?,?,?)",
                (
                    run_id,
                    parent_run_id,
                    created_at,
                    status,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )

    def append_event(
        self,
        *,
        run_id: str,
        kind: str,
        ts: str,
        payload: dict[str, Any],
        step_id: str | None = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO event(run_id,step_id,kind,ts,payload_json) VALUES (?,?,?,?,?)",
                (run_id, step_id, kind, ts, json.dumps(payload, ensure_ascii=False)),
            )

    def record_tool_call_start(
        self,
        *,
        call_id: str,
        run_id: str,
        tool_name: str,
        created_at: str,
        input_payload: dict[str, Any],
        step_id: str | None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO tool_call(call_id,run_id,step_id,tool_name,input_json,status,created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    call_id,
                    run_id,
                    step_id,
                    tool_name,
                    json.dumps(input_payload, ensure_ascii=False),
                    "pending",
                    created_at,
                ),
            )

    def record_tool_call_finish(
        self,
        *,
        call_id: str,
        completed_at: str,
        ok: bool,
        output_payload: dict[str, Any] | None,
        error_payload: dict[str, Any] | None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """UPDATE tool_call
                   SET status=?, output_json=?, error_json=?, completed_at=?
                   WHERE call_id=?""",
                (
                    "success" if ok else "error",
                    json.dumps(output_payload, ensure_ascii=False) if output_payload is not None else None,
                    json.dumps(error_payload, ensure_ascii=False) if error_payload is not None else None,
                    completed_at,
                    call_id,
                ),
            )

    def get_tool_call_output(self, call_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT output_json, status FROM tool_call WHERE call_id=?",
                (call_id,),
            ).fetchone()
            if not row:
                return None
            if row["status"] != "success":
                return None
            out = row["output_json"]
            return json.loads(out) if out else None
