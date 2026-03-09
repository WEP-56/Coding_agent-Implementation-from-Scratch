from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PermissionMode = Literal["readonly", "write", "exec"]


@dataclass(frozen=True, slots=True)
class PermissionPolicy:
    mode: PermissionMode = "readonly"

    def can_read(self) -> bool:
        return True

    def can_write(self) -> bool:
        return self.mode in {"write", "exec"}

    def can_exec(self) -> bool:
        return self.mode == "exec"

    def require_write(self) -> None:
        if not self.can_write():
            raise PermissionError("write permission required")

    def require_exec(self) -> None:
        if not self.can_exec():
            raise PermissionError("exec permission required")
