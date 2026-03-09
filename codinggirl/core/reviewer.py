from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReviewResult:
    ok: bool
    reasons: list[str]
    risk_level: str


def review_patch(patch_text: str, *, max_changed_lines: int = 200) -> ReviewResult:
    reasons: list[str] = []
    changed = 0
    for line in patch_text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            changed += 1
        elif line.startswith("-") and not line.startswith("---"):
            changed += 1

    if "--- " not in patch_text or "+++ " not in patch_text or "@@ " not in patch_text:
        reasons.append("patch is not a valid unified diff")

    if changed > max_changed_lines:
        reasons.append(f"too many changed lines: {changed} > {max_changed_lines}")

    if ".env" in patch_text or "secrets" in patch_text.lower():
        reasons.append("patch touches sensitive-looking files/content")

    ok = len(reasons) == 0
    risk = "low" if ok and changed <= 30 else ("medium" if ok else "high")
    return ReviewResult(ok=ok, reasons=reasons, risk_level=risk)
