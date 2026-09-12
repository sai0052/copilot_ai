"""Mutable in-memory agent state."""

from __future__ import annotations

import time
from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentState(BaseModel):
    task: str
    task_id: int | None = None
    mode: str = "implement"
    phase: Literal[
        "queued",
        "understanding",
        "planning",
        "implementing",
        "testing",
        "analyzing",
        "reviewing",
        "explaining",
        "finalizing",
        "completed",
        "failed",
    ] = "queued"
    plan: list[dict[str, Any]] = Field(default_factory=list)
    files_inspected: list[str] = Field(default_factory=list)
    files_modified: list[str] = Field(default_factory=list)
    commands_executed: list[str] = Field(default_factory=list)
    test_results: list[dict[str, Any]] = Field(default_factory=list)
    iteration: int = 0
    max_iterations: int = 5
    max_tool_rounds: int = 10
    tool_rounds: int = 0
    status: str = "running"
    warnings: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    cancelled: bool = False
    activity: list[str] = Field(default_factory=list)
    problem_description: str | None = None
    root_cause: str | None = None
    project_type: str = "unknown"
    deadline: float | None = None
    started_at: float = Field(default_factory=time.monotonic)
    stop_reason: str | None = None

    def note(self, message: str) -> None:
        self.activity.append(message)

    def timed_out(self) -> bool:
        return self.deadline is not None and time.monotonic() >= self.deadline

    def duration_seconds(self) -> float:
        return max(0.0, time.monotonic() - self.started_at)
