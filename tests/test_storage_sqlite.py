from __future__ import annotations

import uuid
from pathlib import Path

from codinggirl.core.contracts import utc_now_iso
from codinggirl.runtime.storage_sqlite import SQLiteStore


def test_sqlite_store_run_and_event_and_tool_call(tmp_path: Path):
    db = tmp_path / "codinggirl.sqlite3"
    store = SQLiteStore(db)
    store.init_schema()

    run_id = uuid.uuid4().hex
    store.create_run(run_id, created_at=utc_now_iso(), metadata={"goal": "x"})
    store.append_event(run_id=run_id, kind="k", ts=utc_now_iso(), payload={"a": 1})

    call_id = uuid.uuid4().hex
    store.record_tool_call_start(
        call_id=call_id,
        run_id=run_id,
        step_id=None,
        tool_name="fs_read_file",
        created_at=utc_now_iso(),
        input_payload={"args": {"path": "a.txt"}},
    )
    store.record_tool_call_finish(
        call_id=call_id,
        completed_at=utc_now_iso(),
        ok=True,
        output_payload={"content": {"text": "hi"}},
        error_payload=None,
    )

    out = store.get_tool_call_output(call_id)
    assert out == {"content": {"text": "hi"}}
