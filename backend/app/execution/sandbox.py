"""Repository-bounded sandbox for commands and file operations."""

from __future__ import annotations

from pathlib import Path

from app.execution.process import ProcessResult, run_process
from app.utils.security import normalize_repo_root


class Sandbox:
    def __init__(self, root: str | Path) -> None:
        self.root = normalize_repo_root(root)

    def run(self, command: str, timeout: float | None = None) -> ProcessResult:
        return run_process(command, cwd=self.root, timeout=timeout)
