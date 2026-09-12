"""In-process observability counters."""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Any

_lock = threading.Lock()
_counters: dict[str, int] = defaultdict(int)
_timers: dict[str, list[float]] = defaultdict(list)


def incr(name: str, amount: int = 1) -> None:
    with _lock:
        _counters[name] += amount


def observe(name: str, value: float) -> None:
    with _lock:
        _timers[name].append(value)


class Timer:
    def __init__(self, name: str) -> None:
        self.name = name
        self._start = 0.0

    def __enter__(self) -> Timer:
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_exc: object) -> None:
        observe(self.name, time.perf_counter() - self._start)


def snapshot() -> dict[str, Any]:
    with _lock:
        timers = {
            name: {
                "count": len(values),
                "avg_seconds": round(sum(values) / len(values), 4) if values else 0,
                "max_seconds": round(max(values), 4) if values else 0,
            }
            for name, values in _timers.items()
        }
        return {"counters": dict(_counters), "timers": timers}
