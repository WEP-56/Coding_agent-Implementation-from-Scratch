from __future__ import annotations

from fnmatch import fnmatchcase
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from uuid import uuid4


class WorkspaceError(RuntimeError):
    pass


def _is_within_root(root: Path, target: Path) -> bool:
    try:
        target.relative_to(root)
        return True
    except ValueError:
        return False


@dataclass(frozen=True, slots=True)
class RepoWorkspace:
    root: Path

    @staticmethod
    def from_path(path: str | Path) -> "RepoWorkspace":
        root = Path(path).expanduser().resolve(strict=False)
        return RepoWorkspace(root=root)

    def resolve_path(self, rel_path: str) -> Path:
        # Normalize separators and disallow absolute paths early
        p = Path(rel_path)
        if p.is_absolute():
            raise WorkspaceError(f"absolute path not allowed: {rel_path}")
        resolved = (self.root / p).resolve(strict=False)
        if not _is_within_root(self.root, resolved):
            raise WorkspaceError(f"path escapes workspace root: {rel_path}")
        return resolved

    def read_text(self, rel_path: str, *, max_bytes: int = 512_000) -> str:
        p = self.resolve_path(rel_path)
        if not p.exists() or not p.is_file():
            raise WorkspaceError(f"file not found: {rel_path}")
        size = p.stat().st_size
        if size > max_bytes:
            raise WorkspaceError(f"file too large ({size} bytes): {rel_path}")
        return p.read_text(encoding="utf-8", errors="replace")

    def _detect_newline_style(self, p: Path) -> str:
        if not p.exists() or not p.is_file():
            return "\n"
        try:
            with p.open("rb") as f:
                sample = f.read(64_000)
        except OSError:
            return "\n"
        return "\r\n" if b"\r\n" in sample else "\n"

    def default_ignore_patterns(self) -> list[str]:
        return [
            "**/.git/**",
            "**/.hg/**",
            "**/.svn/**",
            "**/.DS_Store",
            "**/.venv/**",
            "**/venv/**",
            "**/node_modules/**",
            "**/__pycache__/**",
            "**/.pytest_cache/**",
            "**/.codinggirl/**",
            "**/tmp/**",
            "**/*.pyc",
            "**/*.pyo",
            "**/*.log",
            "**/*.sqlite3",
            "**/*.sqlite3-wal",
            "**/*.sqlite3-shm",
        ]

    def read_text_range(
        self,
        rel_path: str,
        *,
        start_line: int | None = None,
        end_line: int | None = None,
        offset: int | None = None,
        limit: int | None = None,
        max_lines: int | None = None,
        max_bytes: int = 512_000,
    ) -> dict[str, object]:
        p = self.resolve_path(rel_path)
        if not p.exists() or not p.is_file():
            raise WorkspaceError(f"file not found: {rel_path}")

        def count_total_lines(path: Path) -> int:
            newline_count = 0
            last_byte: bytes | None = None
            saw_any = False
            with path.open("rb") as f:
                while True:
                    chunk = f.read(1024 * 128)
                    if not chunk:
                        break
                    saw_any = True
                    newline_count += chunk.count(b"\n")
                    last_byte = chunk[-1:]
            if not saw_any:
                return 0
            if newline_count == 0:
                return 1
            # If file does not end with '\n', there is a final line without a terminator.
            if last_byte != b"\n":
                return newline_count + 1
            return newline_count

        total_lines = count_total_lines(p)

        if start_line is not None and offset is not None:
            raise WorkspaceError("start_line and offset cannot be used together")
        if end_line is not None and limit is not None:
            raise WorkspaceError("end_line and limit cannot be used together")

        start = start_line if start_line is not None else ((offset or 0) + 1)
        if start < 1:
            raise WorkspaceError("start line must be >= 1")

        end: int | None
        if end_line is not None:
            end = end_line
        elif limit is not None:
            if limit < 0:
                raise WorkspaceError("limit must be >= 0")
            end = start + limit - 1 if limit > 0 else start - 1
        else:
            end = None

        if max_lines is not None:
            if max_lines < 0:
                raise WorkspaceError("max_lines must be >= 0")
            capped_end = start + max_lines - 1 if max_lines > 0 else start - 1
            end = capped_end if end is None else min(end, capped_end)

        if end_line is not None and end_line < start:
            raise WorkspaceError("end_line must be >= start_line")
        if end is not None and end < start - 1:
            raise WorkspaceError("invalid read range")

        output_bytes: Final[int] = max_bytes if max_bytes > 0 else 512_000
        selected_lines: list[str] = []
        used_bytes = 0
        actual_end_line = 0

        # Stream the file so large files are supported.
        with p.open("r", encoding="utf-8", errors="replace", newline=None) as f:
            for line_no, line in enumerate(f, start=1):
                if line_no < start:
                    continue
                if end is not None and line_no > end:
                    break

                normalized = line.rstrip("\n")
                # When newline=None, Python normalizes all newline styles to '\n'.
                encoded_len = len((normalized + "\n").encode("utf-8"))
                if used_bytes + encoded_len > output_bytes:
                    break
                selected_lines.append(normalized)
                used_bytes += encoded_len
                actual_end_line = line_no

        if start > total_lines:
            actual_end_line = total_lines

        effective_end = end if end is not None else (actual_end_line or total_lines)
        truncated = False
        if end is not None:
            truncated = min(end, total_lines) < total_lines
        if max_lines is not None or limit is not None:
            truncated = truncated or (effective_end < total_lines)
        if used_bytes >= output_bytes and (start <= total_lines):
            truncated = True

        return {
            "path": rel_path,
            "text": "\n".join(selected_lines) + ("\n" if selected_lines else ""),
            "start_line": start,
            "end_line": actual_end_line,
            "total_lines": total_lines,
            "truncated": truncated,
            "encoding": "utf-8",
        }

    def write_text(self, rel_path: str, content: str) -> None:
        p = self.resolve_path(rel_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        newline = self._detect_newline_style(p)
        normalized = content.replace("\r\n", "\n").replace("\r", "\n")
        p.write_text(normalized, encoding="utf-8", newline=newline)

    def insert_text_at_line(self, rel_path: str, *, line: int, text: str) -> dict[str, object]:
        if line < 1:
            raise WorkspaceError("line must be >= 1")

        p = self.resolve_path(rel_path)
        if not p.exists() or not p.is_file():
            raise WorkspaceError(f"file not found: {rel_path}")

        newline_out = self._detect_newline_style(p)
        before_size = p.stat().st_size

        def write_with_newline_style(out, chunk: str) -> None:
            normalized = chunk.replace("\r\n", "\n").replace("\r", "\n")
            for part in normalized.splitlines(keepends=True):
                if part.endswith("\n"):
                    out.write(part[:-1])
                    out.write(newline_out)
                else:
                    out.write(part)

        tmp = p.with_name(f"{p.name}.tmp-{uuid4().hex}")
        inserted = False
        current_line = 0

        with p.open("r", encoding="utf-8", errors="replace", newline=None) as src, tmp.open(
            "w", encoding="utf-8", newline=""
        ) as dst:
            for current_line, src_line in enumerate(src, start=1):
                if not inserted and current_line == line:
                    write_with_newline_style(dst, text)
                    inserted = True

                if src_line.endswith("\n"):
                    dst.write(src_line[:-1])
                    dst.write(newline_out)
                else:
                    dst.write(src_line)

            if not inserted:
                if current_line == 0 and line == 1:
                    write_with_newline_style(dst, text)
                    inserted = True
                elif line == current_line + 1:
                    write_with_newline_style(dst, text)
                    inserted = True
                else:
                    raise WorkspaceError(f"line out of range: {line}")

        tmp.replace(p)
        after_size = p.stat().st_size
        return {
            "path": rel_path,
            "line": line,
            "bytes_before": before_size,
            "bytes_after": after_size,
        }

    def glob(
        self,
        pattern: str,
        *,
        path: str = ".",
        recursive: bool = True,
        include_dirs: bool = False,
        ignore: list[str] | None = None,
    ) -> list[dict[str, object]]:
        base = self.resolve_path(path)
        if not base.exists() or not base.is_dir():
            raise WorkspaceError(f"dir not found: {path}")

        ignore_patterns = self._normalize_ignore_patterns(ignore)
        iterator = base.rglob("*") if recursive else base.glob("*")
        results: list[dict[str, object]] = []
        normalized_pattern = pattern.replace("\\", "/")

        for entry in sorted(iterator, key=lambda item: str(item.relative_to(self.root)).lower()):
            if entry.is_dir() and not include_dirs:
                continue
            rel = str(entry.relative_to(self.root)).replace("\\", "/")
            rel_from_base = str(entry.relative_to(base)).replace("\\", "/")
            if ignore_patterns and any(
                fnmatchcase(rel, pat) or fnmatchcase(rel_from_base, pat) for pat in ignore_patterns
            ):
                continue
            if fnmatchcase(rel_from_base, normalized_pattern) or fnmatchcase(rel, normalized_pattern):
                results.append(
                    {
                        "path": rel,
                        "type": "dir" if entry.is_dir() else "file",
                        "size": entry.stat().st_size if entry.is_file() else None,
                    }
                )
        return results

    def replace_text(
        self,
        rel_path: str,
        *,
        old_text: str,
        new_text: str,
        expected_occurrences: int | None = None,
        must_contain: str | list[str] | None = None,
    ) -> dict[str, object]:
        text = self.read_text(rel_path)

        required_tokens = [must_contain] if isinstance(must_contain, str) else (must_contain or [])
        missing = [token for token in required_tokens if token not in text]
        if missing:
            raise WorkspaceError(f"missing required text: {missing[0]}")

        occurrences = text.count(old_text)
        if expected_occurrences is not None and occurrences != expected_occurrences:
            raise WorkspaceError(
                f"expected {expected_occurrences} occurrences of target text, found {occurrences}"
            )
        if occurrences == 0:
            raise WorkspaceError("target text not found")

        updated = text.replace(old_text, new_text)
        self.write_text(rel_path, updated)
        return {
            "path": rel_path,
            "occurrences": occurrences,
            "bytes_before": len(text.encode("utf-8")),
            "bytes_after": len(updated.encode("utf-8")),
        }

    def list_dir(self, rel_path: str = ".") -> list[str]:
        p = self.resolve_path(rel_path)
        if not p.exists() or not p.is_dir():
            raise WorkspaceError(f"dir not found: {rel_path}")
        out: list[str] = []
        for child in sorted(p.iterdir(), key=lambda x: x.name.lower()):
            suffix = "/" if child.is_dir() else ""
            out.append(child.name + suffix)
        return out

    def list_files(
        self,
        rel_path: str = ".",
        *,
        recursive: bool = True,
        include_dirs: bool = False,
        ignore: list[str] | None = None,
        max_results: int = 20_000,
    ) -> list[dict[str, object]]:
        base = self.resolve_path(rel_path)
        if not base.exists() or not base.is_dir():
            raise WorkspaceError(f"dir not found: {rel_path}")

        ignore_patterns = self._normalize_ignore_patterns(ignore)
        results: list[dict[str, object]] = []
        iterator = base.rglob("*") if recursive else base.glob("*")

        for entry in iterator:
            rel = str(entry.relative_to(self.root)).replace("\\", "/")
            rel_from_base = str(entry.relative_to(base)).replace("\\", "/")
            if any(fnmatchcase(rel, pat) or fnmatchcase(rel_from_base, pat) for pat in ignore_patterns):
                continue
            if entry.is_dir():
                if not include_dirs:
                    continue
                results.append({"path": rel, "type": "dir", "size": None})
            elif entry.is_file():
                results.append({"path": rel, "type": "file", "size": entry.stat().st_size})
            if len(results) >= max_results:
                break

        results.sort(key=lambda item: str(item.get("path", "")).lower())
        return results

    def _normalize_ignore_patterns(self, ignore: list[str] | None) -> list[str]:
        raw_ignore = ignore or []
        ignore_patterns: list[str] = []
        for pat in raw_ignore:
            normalized = str(pat).replace("\\", "/")
            ignore_patterns.append(normalized)
            if normalized.startswith("./"):
                ignore_patterns.append(normalized[2:])
            if normalized.startswith("**/"):
                ignore_patterns.append(normalized[3:])
        return ignore_patterns
