"""Structured logging helpers with secret redaction."""

from __future__ import annotations

import logging
import re
import sys
from typing import Any

from app.config import get_settings

_SECRET_PATTERNS = [
    re.compile(r"(api[_-]?key\s*[=:]\s*)([^\s,;]+)", re.I),
    re.compile(r"(authorization:\s*bearer\s+)(\S+)", re.I),
    re.compile(r"(sk-[A-Za-z0-9]{8,})"),
    re.compile(r"(gsk_[A-Za-z0-9]{8,})"),
]


def redact(value: str) -> str:
    redacted = value
    for pattern in _SECRET_PATTERNS:
        if pattern.groups == 2:
            redacted = pattern.sub(r"\1***REDACTED***", redacted)
        else:
            redacted = pattern.sub("***REDACTED***", redacted)
    return redacted


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        if record.args:
            record.args = tuple(redact(str(arg)) if isinstance(arg, str) else arg for arg in record.args)
        return True


def configure_logging() -> None:
    settings = get_settings()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )
    handler.addFilter(RedactingFilter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    payload = " ".join(f"{key}={value}" for key, value in fields.items())
    logger.info("%s %s", event, redact(payload))
