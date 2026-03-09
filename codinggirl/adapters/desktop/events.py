from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


UIState = Literal["idle", "thinking", "success", "error"]


@dataclass(frozen=True, slots=True)
class DesktopEvent:
    kind: str
    payload: dict[str, object]


@dataclass(frozen=True, slots=True)
class AvatarState:
    state: UIState
    emotion: str


def map_run_status_to_avatar(status: str) -> AvatarState:
    if status == "DONE":
        return AvatarState(state="success", emotion="happy")
    if status in {"PATCH_FAILED", "VERIFY_FAILED", "ABORTED"}:
        return AvatarState(state="error", emotion="sad")
    return AvatarState(state="thinking", emotion="neutral")
