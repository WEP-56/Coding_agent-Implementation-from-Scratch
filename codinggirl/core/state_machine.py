from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

RunStatus = Literal[
    "NEW",
    "PLANNED",
    "PATCHED",
    "VERIFIED",
    "APPLIED",
    "DONE",
    "PATCH_FAILED",
    "VERIFY_FAILED",
    "ABORTED",
]


_ALLOWED_TRANSITIONS: dict[RunStatus, set[RunStatus]] = {
    "NEW": {"PLANNED", "ABORTED"},
    "PLANNED": {"PATCHED", "PATCH_FAILED", "ABORTED"},
    "PATCHED": {"VERIFIED", "VERIFY_FAILED", "ABORTED"},
    "VERIFIED": {"APPLIED", "ABORTED"},
    "APPLIED": {"DONE", "ABORTED"},
    "DONE": set(),
    "PATCH_FAILED": {"ABORTED"},
    "VERIFY_FAILED": {"ABORTED"},
    "ABORTED": set(),
}


@dataclass(slots=True)
class RunState:
    run_id: str
    status: RunStatus = "NEW"
    history: list[RunStatus] = field(default_factory=lambda: ["NEW"])

    def transition(self, target: RunStatus) -> None:
        allowed = _ALLOWED_TRANSITIONS[self.status]
        if target not in allowed:
            raise ValueError(f"invalid transition: {self.status} -> {target}")
        self.status = target
        self.history.append(target)
