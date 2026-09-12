"""Test runner built on the sandbox."""

from __future__ import annotations

import re
from pathlib import Path

from app.execution.sandbox import Sandbox


class TestRunner:
    __test__ = False
    def __init__(self, root: str | Path) -> None:
        self.sandbox = Sandbox(root)
        self.root = Path(root)

    def run_tests(self, extra_args: str = "") -> dict:
        command = "pytest -q"
        if extra_args:
            command = f"pytest -q {extra_args}"
        result = self.sandbox.run(command)
        passed, failed = self._parse_pytest(result.stdout + "\n" + result.stderr)
        return {
            "command": result.command,
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration_ms": result.duration_ms,
            "passed": passed,
            "failed": failed,
            "timed_out": result.timed_out,
        }

    def _parse_pytest(self, output: str) -> tuple[int, int]:
        passed = 0
        failed = 0
        match = re.search(r"(\d+)\s+passed", output)
        if match:
            passed = int(match.group(1))
        match = re.search(r"(\d+)\s+failed", output)
        if match:
            failed = int(match.group(1))
        if passed == 0 and failed == 0 and "passed" in output:
            passed = 1
        return passed, failed
