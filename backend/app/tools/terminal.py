"""Terminal tool wrapping the sandbox."""

from __future__ import annotations

from pathlib import Path

from app.execution.sandbox import Sandbox


class TerminalTool:
    def __init__(self, root: str | Path) -> None:
        self.sandbox = Sandbox(root)

    def run_command(self, command: str) -> dict:
        result = self.sandbox.run(command)
        return {
            "command": result.command,
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration_ms": result.duration_ms,
            "timed_out": result.timed_out,
        }
