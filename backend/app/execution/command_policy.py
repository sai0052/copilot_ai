"""Command allowlist and deny patterns."""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass

from app.config import Settings, get_settings

DANGEROUS_PATTERNS = [
    r"\brm\s+-rf\b",
    r"\bdel\s+/[fq]\b",
    r"\bformat\b",
    r"\bmkfs\b",
    r"\bdiskpart\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\breg\s+delete\b",
    r"\bRemove-Item\b",
    r"\brmdir\s+/s\b",
    r"\bcurl\b.+\|\s*(sh|bash)",
    r"\bwget\b.+\|\s*(sh|bash)",
    r"\bcat\s+.*\.env\b",
    r"\btype\s+.*\.env\b",
    r"\bprintenv\b",
    r"\benv\b",
    r"\bset\s+LLM_API_KEY\b",
    r"\bchmod\s+777\b",
    r"\bdd\s+if=",
]


@dataclass
class CommandPolicy:
    allowed: list[str]
    git_allowed_subcommands: tuple[str, ...] = (
        "status",
        "diff",
        "log",
        "rev-parse",
        "checkout",
        "switch",
        "branch",
        "add",
        "restore",
        "show",
    )


class CommandDenied(ValueError):
    pass


def default_policy(settings: Settings | None = None) -> CommandPolicy:
    cfg = settings or get_settings()
    return CommandPolicy(allowed=cfg.allowed_command_list)


def tokenize(command: str) -> list[str]:
    try:
        return shlex.split(command, posix=False)
    except ValueError as exc:
        raise CommandDenied(f"Could not parse command: {exc}") from exc


def validate_command(command: str, policy: CommandPolicy | None = None, repo_root: str | None = None) -> list[str]:
    if not command or not command.strip():
        raise CommandDenied("Empty command")
    lowered = command.strip()
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, lowered, flags=re.I):
            raise CommandDenied(f"Command blocked by security policy: {command}")
    tokens = tokenize(command)
    if not tokens:
        raise CommandDenied("Empty command")
    policy = policy or default_policy()
    binary = tokens[0].lower().replace(".exe", "")
    binary_name = binary.split("\\")[-1].split("/")[-1]
    if binary_name not in policy.allowed:
        raise CommandDenied(f"Command '{binary_name}' is not on the allowlist")
    if binary_name == "git":
        if len(tokens) < 2 or tokens[1] not in policy.git_allowed_subcommands:
            raise CommandDenied("Only a subset of git subcommands is allowed")
        if tokens[1] in {"checkout", "switch", "branch", "restore", "add"} and any(
            token in {"--force", "-f", "--hard"} for token in tokens
        ):
            raise CommandDenied("Destructive git flags are not allowed")
    if binary_name in {"pip", "pip3"} and any(token.lower() == "install" for token in tokens):
        _deny_foreign_framework_install(command, repo_root)
    if ".." in command:
        raise CommandDenied("Parent-directory traversal is not allowed in commands")
    return tokens


_FOREIGN_PACKAGES = ("flask", "django", "fastapi", "starlette")


def _deny_foreign_framework_install(command: str, repo_root: str | None) -> None:
    lowered = command.lower()
    deps = ""
    if repo_root:
        from pathlib import Path

        for name in ("requirements.txt", "pyproject.toml", "Pipfile"):
            path = Path(repo_root) / name
            if path.is_file():
                deps += path.read_text(encoding="utf-8", errors="ignore").lower()
    for package in _FOREIGN_PACKAGES:
        if package in lowered and package not in deps:
            raise CommandDenied(
                f"Installing '{package}' is blocked because this repository does not already use it."
            )
