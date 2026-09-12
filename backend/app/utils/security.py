"""Security helpers: path bounds, secret files, binary detection."""

from __future__ import annotations

import os
from pathlib import Path

SECRET_NAME_PATTERNS = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    "credentials.json",
    "secrets.json",
    "id_rsa",
    "id_ed25519",
    "private.key",
}

SECRET_SUFFIXES = {".pem", ".p12", ".pfx", ".key", ".crt"}

BINARY_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".gz",
    ".tar",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".bin",
    ".pyc",
    ".whl",
    ".woff",
    ".woff2",
    ".ttf",
}


class SecurityError(ValueError):
    """Raised when a requested operation violates repository security rules."""


def resolve_inside_repo(root: str | Path, relative: str | Path) -> Path:
    """Resolve a user-supplied path and ensure it stays inside the repository."""
    repo = normalize_repo_root(root)
    candidate = Path(relative)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (repo / candidate).resolve()
    try:
        resolved.relative_to(repo)
    except ValueError as exc:
        raise SecurityError("Path traversal blocked: target is outside the repository") from exc
    return resolved


def is_secret_file(path: Path) -> bool:
    name = path.name.lower()
    if name in SECRET_NAME_PATTERNS:
        return True
    if name.startswith(".env"):
        return True
    if any(name.endswith(suffix) for suffix in SECRET_SUFFIXES):
        return True
    if "id_rsa" in name or ("private" in name and name.endswith(".key")):
        return True
    return False


def is_blocked_system_path(path: Path) -> bool:
    try:
        resolved = path.expanduser().resolve()
    except OSError:
        resolved = Path(str(path))
    posix = resolved.as_posix().lower()
    raw = str(path).replace("\\", "/").lower()
    if posix.rstrip("/") in {"", "/", "c:", "c:/"} or raw.rstrip("/") in {"/", "c:", "c:/"}:
        return True
    blocked_unix = ("/etc", "/usr", "/bin", "/sbin", "/root", "/dev", "/proc", "/sys", "/boot")
    for prefix in blocked_unix:
        if posix == prefix or posix.startswith(prefix + "/") or raw == prefix or raw.startswith(prefix + "/"):
            return True
    parts = {part.lower() for part in resolved.parts} | {part.lower() for part in Path(raw).parts}
    if parts & {"windows", "system32", "program files", "program files (x86)"}:
        return True
    return False


def sanitize_relative_path(relative: str) -> str:
    raw = relative.replace("\\", "/").strip()
    if not raw or raw.startswith("/") or ":" in raw[:3]:
        raise SecurityError("Absolute paths are not allowed in imports")
    parts = []
    for part in raw.split("/"):
        if part in {"", "."}:
            continue
        if part == ".." or part in {".git", "node_modules", "venv", ".venv", "__pycache__"}:
            if part == "..":
                raise SecurityError("Path traversal blocked")
            raise SecurityError(f"Excluded directory '{part}' cannot be imported")
        parts.append(part)
    if not parts:
        raise SecurityError("Empty import path")
    return "/".join(parts)


def ensure_repo_size_ok(total_bytes: int, max_bytes: int) -> None:
    if total_bytes > max_bytes:
        raise SecurityError(f"Repository exceeds size limit ({total_bytes} > {max_bytes} bytes)")


def normalize_repo_root(root: str | Path) -> Path:
    try:
        path = Path(root).expanduser().resolve()
    except OSError as exc:
        raise SecurityError("Repository folder could not be accessed.") from exc
    try:
        exists = path.exists()
        is_dir = path.is_dir() if exists else False
    except OSError as exc:
        raise SecurityError("Repository folder could not be accessed.") from exc
    if not exists:
        raise SecurityError("Repository path does not exist.")
    if not is_dir:
        raise SecurityError("Repository path is not a directory.")
    if is_blocked_system_path(path):
        raise SecurityError("System directories cannot be used as a project root")
    return path


def is_binary_file(path: Path, sample_size: int = 2048) -> bool:
    if path.suffix.lower() in BINARY_EXTENSIONS:
        return True
    if not path.is_file():
        return False
    try:
        with path.open("rb") as handle:
            chunk = handle.read(sample_size)
        if b"\x00" in chunk:
            return True
    except OSError:
        return True
    return False


def ensure_file_size_ok(path: Path, max_bytes: int) -> None:
    size = path.stat().st_size
    if size > max_bytes:
        raise SecurityError(f"File exceeds size limit ({size} > {max_bytes} bytes): {path.name}")


def redact_env_like(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, _, _value = line.partition("=")
            if any(token in key.upper() for token in ("KEY", "SECRET", "TOKEN", "PASSWORD", "CREDENTIAL")):
                lines.append(f"{key}=***REDACTED***")
                continue
        lines.append(line)
    return "\n".join(lines)


def relative_to_repo(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def env_without_secrets(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Copy process env but drop obvious secret keys before spawning commands."""
    blocked = ("LLM_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GROQ_API_KEY")
    cleaned = {key: value for key, value in os.environ.items() if key not in blocked}
    if extra:
        cleaned.update(extra)
    return cleaned
