"""In-memory SSE event bus per agent task."""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any

_queues: dict[int, list[asyncio.Queue]] = defaultdict(list)
_history: dict[int, list[dict[str, Any]]] = defaultdict(list)


async def publish(task_id: int, event_type: str, message: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    event = {"event": event_type, "message": message, "payload": payload or {}}
    _history[task_id].append(event)
    for queue in list(_queues[task_id]):
        await queue.put(event)
    return event


def history(task_id: int) -> list[dict[str, Any]]:
    return list(_history[task_id])


def subscribe(task_id: int) -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue()
    _queues[task_id].append(queue)
    return queue


def unsubscribe(task_id: int, queue: asyncio.Queue) -> None:
    if queue in _queues[task_id]:
        _queues[task_id].remove(queue)


_cancelled: set[int] = set()


def request_cancel(task_id: int) -> None:
    _cancelled.add(task_id)


def is_cancelled(task_id: int | None) -> bool:
    return bool(task_id is not None and task_id in _cancelled)


def clear_cancel(task_id: int) -> None:
    _cancelled.discard(task_id)


def dump(event: dict[str, Any]) -> str:
    return json.dumps(event)
