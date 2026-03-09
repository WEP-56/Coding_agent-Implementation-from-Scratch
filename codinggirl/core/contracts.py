from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


JSONValue = Any


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    uri: str
    type: str
    sha256: str | None = None


@dataclass(frozen=True, slots=True)
class Task:
    task_id: str
    goal: str
    repo_root: str
    mode: Literal["readonly", "write", "exec"] = "readonly"
    adapter: str = "cli"
    created_at: str = field(default_factory=utc_now_iso)


@dataclass(frozen=True, slots=True)
class PlanStep:
    step_id: str
    title: str
    description: str
    expected_tools: list[str] = field(default_factory=list)
    expected_files: list[str] = field(default_factory=list)
    exit_criteria: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Plan:
    task_id: str
    assumptions: list[str] = field(default_factory=list)
    steps: list[PlanStep] = field(default_factory=list)
    exit_criteria: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)


@dataclass(frozen=True, slots=True)
class PatchFile:
    path: str
    unified_diff: str
    checksum_before: str | None = None
    checksum_after: str | None = None


@dataclass(frozen=True, slots=True)
class PatchSet:
    format: Literal["unified-diff"]
    files: list[PatchFile]


@dataclass(frozen=True, slots=True)
class ToolCall:
    call_id: str
    tool_name: str
    args: dict[str, JSONValue]
    timeout_ms: int = 120_000
    risk_level: Literal["low", "medium", "high"] = "low"
    created_at: str = field(default_factory=utc_now_iso)


@dataclass(frozen=True, slots=True)
class ToolResult:
    call_id: str
    tool_name: str
    ok: bool
    content: JSONValue | None = None
    stdout: str | None = None
    stderr: str | None = None
    error: str | None = None
    artifacts: list[ArtifactRef] = field(default_factory=list)
    completed_at: str = field(default_factory=utc_now_iso)


@dataclass(frozen=True, slots=True)
class Event:
    run_id: str
    kind: str
    payload: dict[str, JSONValue]
    step_id: str | None = None
    ts: str = field(default_factory=utc_now_iso)


def to_jsonable(obj: Any) -> Any:
    """Convert dataclasses to plain JSON-serializable structures."""
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    return obj
