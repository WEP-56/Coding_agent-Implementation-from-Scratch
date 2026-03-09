from __future__ import annotations

from dataclasses import dataclass
import re

from codinggirl.adapters.telegram.session_store import TelegramSession, TelegramSessionStore
from codinggirl.core.orchestrator import execute_goal
from codinggirl.core.policy import PermissionPolicy


@dataclass(frozen=True, slots=True)
class TelegramReply:
    text: str


def _default_session(chat_id: str) -> TelegramSession:
    return TelegramSession(
        chat_id=chat_id,
        repo_root=".",
        db_path=".codinggirl/codinggirl.sqlite3",
        mode="readonly",
    )


def _split_command(text: str) -> tuple[str, str]:
    stripped = text.strip()
    if not stripped:
        return "", ""
    parts = stripped.split(maxsplit=1)
    raw_cmd = parts[0]
    rest = parts[1] if len(parts) > 1 else ""

    # Git Bash / MSYS may rewrite '/cmd' into path-like strings.
    token = raw_cmd
    if token.startswith("/"):
        token = token[1:]
    # handle path-rewritten command tokens from shells (/, \\, or drive-style)
    if "/" in token or "\\" in token:
        token = re.split(r"[\\/]", token)[-1]
    if ":" in token:
        token = token.split(":")[-1]

    cmd = token
    return cmd.lower(), rest.strip()


def handle_message(*, store: TelegramSessionStore, chat_id: str, text: str) -> TelegramReply:
    session = store.get(chat_id) or _default_session(chat_id)
    policy = PermissionPolicy(mode=session.mode)

    cmd, rest = _split_command(text)

    if cmd == "start":
        store.upsert(session)
        return TelegramReply(
            "CodingGirl Telegram adapter ready. Use /set_repo, /set_mode, /goal, /whoami"
        )

    if cmd == "whoami":
        return TelegramReply(
            f"chat_id={session.chat_id}\nrepo={session.repo_root}\nmode={session.mode}\ndb={session.db_path}"
        )

    if cmd == "set_repo":
        repo = rest
        if not repo:
            return TelegramReply("usage: /set_repo <path>")
        next_session = TelegramSession(
            chat_id=session.chat_id,
            repo_root=repo,
            db_path=session.db_path,
            mode=session.mode,
        )
        store.upsert(next_session)
        return TelegramReply(f"repo updated: {repo}")

    if cmd == "set_mode":
        mode = rest.lower()
        if mode not in {"readonly", "write", "exec"}:
            return TelegramReply("usage: /set_mode readonly|write|exec")
        next_session = TelegramSession(
            chat_id=session.chat_id,
            repo_root=session.repo_root,
            db_path=session.db_path,
            mode=mode,  # type: ignore[arg-type]
        )
        store.upsert(next_session)
        return TelegramReply(f"mode updated: {mode}")

    if cmd == "goal":
        goal = rest
        if not goal:
            return TelegramReply("usage: /goal replace [old] with [new] in [path]")
        try:
            policy.require_write()
        except PermissionError as e:
            return TelegramReply(f"permission denied: {e}")

        result = execute_goal(
            repo_root=session.repo_root,
            goal=goal,
            db_path=session.db_path,
        )
        return TelegramReply(
            f"run_id={result.run_id}\nstatus={result.status}\nmessage={result.message}"
        )

    return TelegramReply("unknown command. try /start")
