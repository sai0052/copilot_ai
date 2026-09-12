"""Import a browser-selected folder into a local workspace, preserving structure."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from app.config import Settings, get_settings
from app.utils.security import (
    SecurityError,
    ensure_file_size_ok,
    ensure_repo_size_ok,
    is_secret_file,
    sanitize_relative_path,
)


class ImportedFile:
    def __init__(self, path: str, content: str) -> None:
        self.path = path
        self.content = content


def import_files_to_workspace(
    project_name: str,
    files: list[tuple[str, str]],
    settings: Settings | None = None,
) -> Path:
    cfg = settings or get_settings()
    if not files:
        raise SecurityError("Unable to read project. No files were provided.")
    if len(files) > cfg.import_max_files:
        raise SecurityError(f"Project contains too many files ({len(files)} > {cfg.import_max_files}).")

    safe_name = _safe_name(project_name)
    root = (cfg.data_dir / "workspaces" / uuid.uuid4().hex[:12] / safe_name).resolve()
    root.mkdir(parents=True, exist_ok=True)
    total = 0
    written = 0
    for raw_path, content in files:
        relative = sanitize_relative_path(raw_path)
        target = (root / relative).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise SecurityError("Path traversal blocked") from exc
        if is_secret_file(target):
            continue
        encoded = content.encode("utf-8")
        if len(encoded) > cfg.import_max_file_bytes:
            raise SecurityError(f"File exceeds size limit: {relative}")
        total += len(encoded)
        ensure_repo_size_ok(total, cfg.import_max_repo_bytes)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written += 1
        ensure_file_size_ok(target, cfg.import_max_file_bytes)
    if written == 0:
        raise SecurityError("Unable to read project. Every file was excluded or empty.")
    return root


def _safe_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", name.strip())[:80].strip(".-")
    return cleaned or "project"
