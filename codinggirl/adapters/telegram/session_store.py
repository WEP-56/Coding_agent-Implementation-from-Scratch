from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from codinggirl.core.policy import PermissionMode


@dataclass(frozen=True, slots=True)
class TelegramSession:
    chat_id: str
    repo_root: str
    db_path: str
    mode: PermissionMode


@dataclass(frozen=True, slots=True)
class TelegramSessionStore:
    path: Path

    def _load_all(self) -> dict[str, dict[str, str]]:
        if not self.path.exists():
            return {}
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {}
        out: dict[str, dict[str, str]] = {}
        for k, v in raw.items():
            if isinstance(k, str) and isinstance(v, dict):
                out[k] = {str(kk): str(vv) for kk, vv in v.items()}
        return out

    def _save_all(self, payload: dict[str, dict[str, str]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def get(self, chat_id: str) -> TelegramSession | None:
        data = self._load_all()
        item = data.get(chat_id)
        if not item:
            return None
        mode = item.get("mode", "readonly")
        if mode not in {"readonly", "write", "exec"}:
            mode = "readonly"
        return TelegramSession(
            chat_id=chat_id,
            repo_root=item.get("repo_root", "."),
            db_path=item.get("db_path", ".codinggirl/codinggirl.sqlite3"),
            mode=mode,  # type: ignore[arg-type]
        )

    def upsert(self, session: TelegramSession) -> None:
        data = self._load_all()
        data[session.chat_id] = {
            "repo_root": session.repo_root,
            "db_path": session.db_path,
            "mode": session.mode,
        }
        self._save_all(data)
