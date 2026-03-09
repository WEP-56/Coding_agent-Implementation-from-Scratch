from __future__ import annotations

from pathlib import Path

from codinggirl.adapters.telegram.handler import handle_message
from codinggirl.adapters.telegram.session_store import TelegramSessionStore


def test_telegram_session_isolation(tmp_path: Path):
    store = TelegramSessionStore(tmp_path / "sessions.json")

    r1 = handle_message(store=store, chat_id="100", text="/start")
    assert "ready" in r1.text
    handle_message(store=store, chat_id="100", text="/set_repo repo_a")

    r2 = handle_message(store=store, chat_id="200", text="/start")
    assert "ready" in r2.text
    who_100 = handle_message(store=store, chat_id="100", text="/whoami")
    who_200 = handle_message(store=store, chat_id="200", text="/whoami")

    assert "repo=repo_a" in who_100.text
    assert "repo=." in who_200.text


def test_telegram_goal_denied_in_readonly(tmp_path: Path):
    store = TelegramSessionStore(tmp_path / "sessions.json")
    handle_message(store=store, chat_id="1", text="/start")
    r = handle_message(store=store, chat_id="1", text="/goal replace [a] with [b] in [x.txt]")
    assert "permission denied" in r.text


def test_telegram_goal_success_in_write_mode(tmp_path: Path):
    (tmp_path / "x.txt").write_text("hello old\n", encoding="utf-8")
    store = TelegramSessionStore(tmp_path / "sessions.json")
    handle_message(store=store, chat_id="1", text="/start")
    handle_message(store=store, chat_id="1", text=f"/set_repo {tmp_path}")
    handle_message(store=store, chat_id="1", text="/set_mode write")

    r = handle_message(store=store, chat_id="1", text="/goal replace [old] with [new] in [x.txt]")
    assert "status=DONE" in r.text
    assert "new" in (tmp_path / "x.txt").read_text(encoding="utf-8")
