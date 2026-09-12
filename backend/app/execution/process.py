"""Process execution with timeouts and output caps."""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings, get_settings
from app.execution.command_policy import validate_command
from app.utils.security import env_without_secrets

MODULE_COMMANDS = {
    "pytest": ["-m", "pytest"],
    "pip": ["-m", "pip"],
    "pip3": ["-m", "pip"],
}


@dataclass
class ProcessResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False


def _clip(text: str, max_bytes: int) -> str:
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode("utf-8", errors="replace") + "\n...[truncated]"


def resolve_argv(tokens: list[str]) -> list[str]:
    binary = tokens[0].lower().replace(".exe", "")
    name = Path(binary).name
    rest = tokens[1:]
    if name in {"python", "python3"}:
        return [sys.executable, *rest]
    if name in MODULE_COMMANDS:
        return [sys.executable, *MODULE_COMMANDS[name], *rest]
    located = shutil.which(tokens[0])
    if located:
        return [located, *rest]
    return tokens


def run_process(
    command: str,
    cwd: Path,
    settings: Settings | None = None,
    timeout: float | None = None,
) -> ProcessResult:
    cfg = settings or get_settings()
    tokens = resolve_argv(validate_command(command, repo_root=str(cwd)))
    started = time.perf_counter()
    timed_out = False
    try:
        completed = subprocess.run(
            tokens,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout or cfg.command_timeout_seconds,
            env=env_without_secrets({"PYTHONUNBUFFERED": "1"}),
            check=False,
        )
        exit_code = completed.returncode
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
    except FileNotFoundError:
        return ProcessResult(
            command=command,
            exit_code=127,
            stdout="",
            stderr=f"Command not found: {tokens[0]}",
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = 124
        stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        stderr = ((exc.stderr or "") if isinstance(exc.stderr, str) else "") + "\nCommand timed out"
    duration_ms = int((time.perf_counter() - started) * 1000)
    return ProcessResult(
        command=command,
        exit_code=exit_code,
        stdout=_clip(stdout, cfg.command_output_max_bytes),
        stderr=_clip(stderr, cfg.command_output_max_bytes),
        duration_ms=duration_ms,
        timed_out=timed_out,
    )
