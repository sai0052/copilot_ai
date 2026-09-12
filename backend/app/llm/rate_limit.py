"""Centralized wait policy for Groq/OpenAI-compatible 429 and transient failures."""

from __future__ import annotations

import random
import re
from typing import Any

MAX_RETRY_AFTER = 120.0
_RETRY_IN_RE = re.compile(r"try again in ([\d.]+)\s*s", re.I)


def compute_wait_seconds(
    *,
    retry_after: str | None,
    body: str = "",
    retry_index: int = 0,
    base_seconds: float = 5.0,
    jitter: float = 0.0,
) -> float:
    """Retry-After wins; otherwise exponential backoff (5, 10, 20, ...) with optional jitter."""
    parsed = _parse_retry_after(retry_after) if retry_after else None
    if parsed is None:
        parsed = _parse_retry_from_body(body)
    if parsed is not None:
        return min(MAX_RETRY_AFTER, max(0.0, parsed))
    wait = min(MAX_RETRY_AFTER, max(0.0, float(base_seconds) * (2**retry_index)))
    if jitter and wait > 0:
        spread = min(abs(float(jitter)), 0.5)
        wait = wait * random.uniform(1.0 - spread, 1.0 + spread)
    return min(MAX_RETRY_AFTER, wait)


def public_wait_label(seconds: float) -> str:
    shown = max(1, int(round(seconds)))
    return f"Waiting {shown} seconds before retry..."


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _parse_retry_from_body(text: str) -> float | None:
    match = _RETRY_IN_RE.search(text or "")
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def redact_provider_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    data = dict(payload or {})
    data.pop("api_key", None)
    data.pop("authorization", None)
    return data
