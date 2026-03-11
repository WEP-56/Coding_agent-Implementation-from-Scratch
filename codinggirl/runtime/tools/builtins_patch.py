from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from codinggirl.core.contracts import ToolCall, ToolResult
from codinggirl.runtime.workspace import RepoWorkspace, WorkspaceError


class PatchError(RuntimeError):
    pass


class PatchConflict(PatchError):
    def __init__(self, message: str, *, details: dict[str, Any]) -> None:
        super().__init__(message)
        self.details = details


@dataclass(frozen=True, slots=True)
class Hunk:
    old_start: int
    old_len: int
    new_start: int
    new_len: int
    lines: list[str]


@dataclass(frozen=True, slots=True)
class FilePatch:
    old_path: str
    new_path: str
    hunks: list[Hunk]


_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _strip_prefix(path: str) -> str:
    # Git-style diffs often use a/ and b/ prefixes.
    if path.startswith("a/") or path.startswith("b/"):
        return path[2:]
    return path


def parse_unified_diff(patch: str) -> list[FilePatch]:
    lines = patch.splitlines()
    i = 0
    out: list[FilePatch] = []
    while i < len(lines):
        line = lines[i]
        if not line.startswith("--- "):
            i += 1
            continue
        old_path = line[4:].strip()
        i += 1
        if i >= len(lines) or not lines[i].startswith("+++ "):
            raise PatchError("invalid patch: missing +++")
        new_path = lines[i][4:].strip()
        i += 1

        hunks: list[Hunk] = []
        while i < len(lines):
            if lines[i].startswith("--- "):
                break
            m = _HUNK_RE.match(lines[i])
            if not m:
                i += 1
                continue
            old_start = int(m.group(1))
            old_len = int(m.group(2) or "1")
            new_start = int(m.group(3))
            new_len = int(m.group(4) or "1")
            i += 1
            hunk_lines: list[str] = []
            while i < len(lines) and not lines[i].startswith("@@ ") and not lines[i].startswith("--- "):
                hunk_lines.append(lines[i])
                i += 1
            hunks.append(
                Hunk(
                    old_start=old_start,
                    old_len=old_len,
                    new_start=new_start,
                    new_len=new_len,
                    lines=hunk_lines,
                )
            )

        out.append(FilePatch(old_path=old_path, new_path=new_path, hunks=hunks))
    return out


def apply_file_patch(
    *,
    original: list[str],
    file_patch: FilePatch,
) -> list[str]:
    # Apply hunks sequentially using old_start + a running delta.
    lines = list(original)
    delta = 0
    for hunk_index, h in enumerate(file_patch.hunks):
        idx = (h.old_start - 1) + delta
        if idx < 0 or idx > len(lines):
            raise PatchConflict(
                f"hunk out of range at old_start={h.old_start}",
                details={
                    "kind": "hunk_out_of_range",
                    "old_start": h.old_start,
                    "old_len": h.old_len,
                    "new_start": h.new_start,
                    "new_len": h.new_len,
                    "hunk_index": hunk_index,
                },
            )

        for hunk_line_index, hl in enumerate(h.lines):
            if hl.startswith("\\"):
                # e.g. "\\ No newline at end of file" - ignore
                continue
            if not hl:
                prefix = " "
                content = ""
            else:
                prefix = hl[0]
                content = hl[1:]

            if prefix == " ":
                if idx >= len(lines) or lines[idx] != content:
                    actual = "<EOF>" if idx >= len(lines) else lines[idx]
                    raise PatchConflict(
                        "context mismatch",
                        details={
                            "kind": "context_mismatch",
                            "expected": content,
                            "actual": actual,
                            "old_start": h.old_start,
                            "old_len": h.old_len,
                            "new_start": h.new_start,
                            "new_len": h.new_len,
                            "hunk_index": hunk_index,
                            "hunk_line_index": hunk_line_index,
                            "file_old_path": file_patch.old_path,
                            "file_new_path": file_patch.new_path,
                        },
                    )
                idx += 1
            elif prefix == "-":
                if idx >= len(lines) or lines[idx] != content:
                    actual = "<EOF>" if idx >= len(lines) else lines[idx]
                    raise PatchConflict(
                        "delete mismatch",
                        details={
                            "kind": "delete_mismatch",
                            "expected": content,
                            "actual": actual,
                            "old_start": h.old_start,
                            "old_len": h.old_len,
                            "new_start": h.new_start,
                            "new_len": h.new_len,
                            "hunk_index": hunk_index,
                            "hunk_line_index": hunk_line_index,
                            "file_old_path": file_patch.old_path,
                            "file_new_path": file_patch.new_path,
                        },
                    )
                del lines[idx]
                delta -= 1
            elif prefix == "+":
                lines.insert(idx, content)
                idx += 1
                delta += 1
            else:
                raise PatchConflict(
                    f"invalid hunk line prefix: {prefix!r}",
                    details={
                        "kind": "invalid_hunk_prefix",
                        "prefix": prefix,
                        "old_start": h.old_start,
                        "old_len": h.old_len,
                        "new_start": h.new_start,
                        "new_len": h.new_len,
                        "hunk_index": hunk_index,
                        "hunk_line_index": hunk_line_index,
                        "file_old_path": file_patch.old_path,
                        "file_new_path": file_patch.new_path,
                    },
                )

    return lines


def make_patch_apply_unified_diff(workspace: RepoWorkspace):
    def handler(call: ToolCall) -> ToolResult:
        patch_text = str(call.args["patch"])
        allow_delete = bool(call.args.get("allow_delete", False))
        do_backup = bool(call.args.get("backup", True))
        backup_dir = str(call.args.get("backup_dir", ".codinggirl/backups"))
        dry_run = bool(call.args.get("dry_run", False))

        file_patches = parse_unified_diff(patch_text)
        if not file_patches:
            return ToolResult(call_id=call.call_id, tool_name=call.tool_name, ok=False, error="empty patch")

        staged: list[dict[str, object]] = []
        results: list[dict[str, object]] = []

        try:
            for fp in file_patches:
                old_path = fp.old_path
                new_path = fp.new_path

                if old_path == "/dev/null":
                    before_lines: list[str] = []
                    target = _strip_prefix(new_path)
                    before_text_full = ""
                elif new_path == "/dev/null":
                    if not allow_delete:
                        raise PatchError("delete file not allowed")
                    target = _strip_prefix(old_path)
                    before_text = workspace.read_text(target)
                    results.append(
                        {"path": target, "op": "delete", "sha256_before": _sha256_text(before_text)}
                    )
                    staged.append({"path": target, "op": "delete", "before": before_text})
                    continue
                else:
                    target = _strip_prefix(new_path)
                    before_text = workspace.read_text(target)
                    before_lines = before_text.splitlines()
                    before_text_full = "\n".join(before_lines) + ("\n" if before_lines else "")

                after_lines = apply_file_patch(original=before_lines, file_patch=fp)
                after_text = "\n".join(after_lines) + ("\n" if after_lines else "")

                staged.append(
                    {
                        "path": target,
                        "op": "modify" if old_path != "/dev/null" else "add",
                        "before": before_text_full,
                        "after": after_text,
                    }
                )
                results.append(
                    {
                        "path": target,
                        "op": "modify" if old_path != "/dev/null" else "add",
                        "sha256_before": _sha256_text(before_text_full),
                        "sha256_after": _sha256_text(after_text),
                    }
                )

            if dry_run:
                return ToolResult(
                    call_id=call.call_id,
                    tool_name=call.tool_name,
                    ok=True,
                    content={"dry_run": True, "files": results},
                )

            # All staged clean → apply (and only then create backups)
            if do_backup:
                bp = workspace.resolve_path(backup_dir)
                bp.mkdir(parents=True, exist_ok=True)
                for action in staged:
                    if action["op"] != "modify":
                        continue
                    target = str(action["path"])
                    before = str(action["before"])
                    backup_file = (bp / (target.replace("/", "__") + ".bak"))
                    newline = workspace._detect_newline_style(workspace.resolve_path(target))
                    backup_file.write_text(before, encoding="utf-8", newline=newline)
                    for r in results:
                        if r.get("path") == target and r.get("op") == "modify":
                            r["backup"] = str(Path(backup_dir) / backup_file.name)
                            break

            for action in staged:
                op = str(action["op"])
                target = str(action["path"])
                if op == "delete":
                    p = workspace.resolve_path(target)
                    if p.exists():
                        p.unlink()
                    continue
                workspace.write_text(target, str(action["after"]))

        except PatchConflict as e:
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                ok=False,
                error=str(e),
                content={"conflict": e.details},
            )
        except (PatchError, WorkspaceError) as e:
            return ToolResult(call_id=call.call_id, tool_name=call.tool_name, ok=False, error=str(e))

        return ToolResult(call_id=call.call_id, tool_name=call.tool_name, ok=True, content={"files": results, "dry_run": False})

    return handler
