"""Controlled filesystem operations with snapshots and syntax checks."""

from __future__ import annotations

import ast
import difflib
from pathlib import Path

from app.config import get_settings
from app.utils.security import (
    SecurityError,
    ensure_file_size_ok,
    is_binary_file,
    is_secret_file,
    relative_to_repo,
    resolve_inside_repo,
)


class FileSystemTools:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.settings = get_settings()

    def list_files(self, directory: str = ".", glob: str = "*") -> list[str]:
        target = resolve_inside_repo(self.root, directory)
        if not target.exists():
            raise SecurityError(f"Directory not found: {directory}")
        if target.is_file():
            return [relative_to_repo(self.root, target)]
        results = []
        for path in sorted(target.glob(glob)):
            if path.is_file() and not is_secret_file(path) and not is_binary_file(path):
                results.append(relative_to_repo(self.root, path))
        return results[:500]

    def read_file(self, path: str) -> str:
        target = resolve_inside_repo(self.root, path)
        if not target.exists() or not target.is_file():
            raise SecurityError(f"File not found: {path}")
        if is_secret_file(target):
            raise SecurityError("Refusing to read secret file")
        if is_binary_file(target):
            raise SecurityError("Refusing to read binary file")
        ensure_file_size_ok(target, self.settings.file_max_bytes)
        return target.read_text(encoding="utf-8", errors="replace")

    def write_file(self, path: str, content: str) -> str:
        target = resolve_inside_repo(self.root, path)
        if is_secret_file(target):
            raise SecurityError("Refusing to write secret file")
        target.parent.mkdir(parents=True, exist_ok=True)
        previous = target.read_text(encoding="utf-8", errors="replace") if target.exists() else ""
        self._snapshot(path, previous)
        target.write_text(content, encoding="utf-8")
        self._validate_syntax(target, content)
        return self._diff(path, previous, content)

    def patch_file(self, path: str, old: str, new: str) -> str:
        current = self.read_file(path)
        if old not in current:
            raise SecurityError("Patch context not found in file")
        if current.count(old) != 1:
            raise SecurityError("Patch context is not unique; provide more surrounding lines")
        updated = current.replace(old, new, 1)
        return self.write_file(path, updated)

    def insert_after(self, path: str, anchor: str, insertion: str) -> str:
        current = self.read_file(path)
        if anchor not in current:
            raise SecurityError("Insert anchor not found")
        updated = current.replace(anchor, anchor + insertion, 1)
        return self.write_file(path, updated)

    def delete_file(self, path: str) -> str:
        target = resolve_inside_repo(self.root, path)
        if is_secret_file(target):
            raise SecurityError("Refusing to delete secret file")
        if not target.exists():
            raise SecurityError(f"File not found: {path}")
        previous = target.read_text(encoding="utf-8", errors="replace") if target.is_file() else ""
        self._snapshot(path, previous)
        if target.is_file():
            target.unlink()
        return self._diff(path, previous, "")

    def _snapshot(self, relative: str, content: str) -> None:
        folder = self.root / ".codepilot_snapshots"
        folder.mkdir(parents=True, exist_ok=True)
        safe_name = relative.replace("/", "__").replace("\\", "__")
        (folder / safe_name).write_text(content, encoding="utf-8")

    def _validate_syntax(self, path: Path, content: str) -> None:
        if path.suffix == ".py":
            ast.parse(content)

    def _diff(self, path: str, previous: str, current: str) -> str:
        return "".join(
            difflib.unified_diff(
                previous.splitlines(keepends=True),
                current.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
            )
        )
