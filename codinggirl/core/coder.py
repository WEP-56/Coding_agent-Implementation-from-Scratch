from __future__ import annotations

import difflib
import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReplaceInstruction:
    file: str
    old: str
    new: str


_REPLACE_RE = re.compile(
    r"replace\s+\[(?P<old>.*?)\]\s+with\s+\[(?P<new>.*?)\]\s+in\s+\[(?P<file>.*?)\]",
    re.IGNORECASE | re.DOTALL,
)


def parse_replace_goal(goal: str) -> ReplaceInstruction:
    m = _REPLACE_RE.search(goal)
    if not m:
        raise ValueError(
            "unsupported goal format; expected: replace [old] with [new] in [path]"
        )
    old = m.group("old")
    new = m.group("new")
    file = m.group("file").strip()
    if not file:
        raise ValueError("target file cannot be empty")
    return ReplaceInstruction(file=file, old=old, new=new)


def make_unified_diff_for_replace(*, path: str, before_text: str, old: str, new: str) -> str:
    if old not in before_text:
        raise ValueError("old text not found in target file")

    after_text = before_text.replace(old, new, 1)
    before_lines = before_text.splitlines()
    after_lines = after_text.splitlines()

    diff_lines = list(
        difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
    )
    if not diff_lines:
        raise ValueError("no diff generated")
    return "\n".join(diff_lines) + "\n"
