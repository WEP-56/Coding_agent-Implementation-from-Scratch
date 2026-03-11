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
_DIFF_GIT_RE = re.compile(r"^diff --git (.+?) (.+?)$")


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
    current_old: str | None = None
    current_new: str | None = None
    current_rename_from: str | None = None
    current_rename_to: str | None = None
    current_hunks: list[Hunk] = []

    def flush_current() -> None:
        nonlocal current_old, current_new, current_rename_from, current_rename_to, current_hunks
        if current_old is None and current_new is None:
            current_hunks = []
            current_rename_from = None
            current_rename_to = None
            return

        old_path = current_old
        new_path = current_new
        if old_path is None and current_rename_from is not None:
            old_path = current_rename_from
        if new_path is None and current_rename_to is not None:
            new_path = current_rename_to

        if old_path is not None and new_path is not None:
            out.append(FilePatch(old_path=old_path, new_path=new_path, hunks=current_hunks))

        current_old = None
        current_new = None
        current_rename_from = None
        current_rename_to = None
        current_hunks = []

    while i < len(lines):
        line = lines[i]
        m_diff = _DIFF_GIT_RE.match(line)
        if m_diff:
            flush_current()
            current_old = m_diff.group(1).strip()
            current_new = m_diff.group(2).strip()
            i += 1
            continue

        if line.startswith("rename from "):
            current_rename_from = line[len("rename from ") :].strip()
            i += 1
            continue
        if line.startswith("rename to "):
            current_rename_to = line[len("rename to ") :].strip()
            i += 1
            continue

        if line.startswith("--- "):
            current_old = line[4:].strip()
            i += 1
            if i >= len(lines) or not lines[i].startswith("+++ "):
                raise PatchError("invalid patch: missing +++")
            current_new = lines[i][4:].strip()
            i += 1
            continue

        m = _HUNK_RE.match(line)
        if m:
            old_start = int(m.group(1))
            old_len = int(m.group(2) or "1")
            new_start = int(m.group(3))
            new_len = int(m.group(4) or "1")
            i += 1
            hunk_lines: list[str] = []
            while i < len(lines):
                if _HUNK_RE.match(lines[i]) or lines[i].startswith("diff --git ") or lines[i].startswith("--- "):
                    break
                hunk_lines.append(lines[i])
                i += 1
            current_hunks.append(
                Hunk(
                    old_start=old_start,
                    old_len=old_len,
                    new_start=new_start,
                    new_len=new_len,
                    lines=hunk_lines,
                )
            )
            continue

        i += 1

    flush_current()
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
                old_target = None if old_path == "/dev/null" else _strip_prefix(old_path)
                new_target = None if new_path == "/dev/null" else _strip_prefix(new_path)

                if new_target is not None and old_target is not None and old_target != new_target:
                    # Rename (possibly with edits).
                    old_exists = workspace.resolve_path(old_target).exists()
                    if not old_exists:
                        raise PatchError(f"file not found: {old_target}")
                    if workspace.resolve_path(new_target).exists():
                        raise PatchError(f"target already exists: {new_target}")

                if old_path == "/dev/null":
                    before_lines = []
                    if new_target is None:
                        raise PatchError("invalid add patch")
                    if workspace.resolve_path(new_target).exists():
                        raise PatchError(f"target already exists: {new_target}")
                    before_text_full = ""
                elif new_path == "/dev/null":
                    if not allow_delete:
                        raise PatchError("delete file not allowed")
                    if old_target is None:
                        raise PatchError("invalid delete patch")
                    before_text = workspace.read_text(old_target)
                    results.append(
                        {"path": old_target, "op": "delete", "sha256_before": _sha256_text(before_text)}
                    )
                    staged.append({"path": old_target, "op": "delete", "before": before_text})
                    continue
                else:
                    if old_target is None or new_target is None:
                        raise PatchError("invalid modify patch")
                    source_path = old_target
                    before_text = workspace.read_text(source_path)
                    before_lines = before_text.splitlines()
                    before_text_full = "\n".join(before_lines) + ("\n" if before_lines else "")

                after_lines = apply_file_patch(original=before_lines, file_patch=fp)
                after_text = "\n".join(after_lines) + ("\n" if after_lines else "")

                staged.append(
                    {
                        "path": new_target,
                        "op": "modify" if old_path != "/dev/null" else "add",
                        "before": before_text_full,
                        "after": after_text,
                        "source_path": old_target,
                    }
                )
                results.append(
                    {
                        "path": new_target,
                        "op": "modify" if old_path != "/dev/null" else "add",
                        "sha256_before": _sha256_text(before_text_full),
                        "sha256_after": _sha256_text(after_text),
                    }
                )
                if old_target is not None and new_target is not None and old_target != new_target:
                    results[-1]["op"] = "rename"
                    results[-1]["old_path"] = old_target
                    staged[-1]["op"] = "rename"

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
                    if action["op"] not in ("modify", "rename"):
                        continue
                    source_path = str(action.get("source_path") or action["path"])
                    target = str(action["path"])
                    before = str(action["before"])
                    backup_file = (bp / (target.replace("/", "__") + ".bak"))
                    newline = workspace._detect_newline_style(workspace.resolve_path(source_path))
                    backup_file.write_text(before, encoding="utf-8", newline=newline)
                    for r in results:
                        if r.get("path") == target and r.get("op") in ("modify", "rename"):
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

                source_path = action.get("source_path")
                if source_path and str(source_path) != target:
                    # Rename first to preserve newline style on the new path.
                    src = workspace.resolve_path(str(source_path))
                    dst = workspace.resolve_path(target)
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    src.replace(dst)
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
