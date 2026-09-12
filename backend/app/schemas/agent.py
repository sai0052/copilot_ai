"""Agent API and domain schemas."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import AliasChoices, BaseModel, Field, field_validator


class AgentMode(str, Enum):
    IMPLEMENT = "implement"
    REVIEW = "review"
    EXPLAIN = "explain"
    ISSUE = "issue"


class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    LIMIT_REACHED = "limit_reached"
    TIMEOUT = "timeout"
    NEEDS_REVIEW = "needs_review"


class PlanStep(BaseModel):
    index: int
    title: str
    detail: str
    status: str = "PENDING"
    id: int | None = None
    kind: str | None = None

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, value: object) -> str:
        from app.agent.plan_progress import normalize_status

        return normalize_status(str(value) if value is not None else "PENDING")


class ImplementationPlan(BaseModel):
    summary: str
    steps: list[PlanStep]
    relevant_files: list[str] = Field(default_factory=list)
    tests_to_run: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class FailureDiagnosis(BaseModel):
    root_cause: str
    affected_files: list[str]
    proposed_fix: str
    confidence: float = Field(ge=0, le=1)


class FinalReport(BaseModel):
    task: str
    status: str
    summary: str
    files_changed: list[str] = Field(default_factory=list)
    tests_executed: str = ""
    tests_passed: int = 0
    tests_failed: int = 0
    commands_executed: list[str] = Field(default_factory=list)
    iterations_used: int = 0
    tool_rounds: int = 0
    duration_seconds: float = 0.0
    decisions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    review_findings: list[dict[str, Any]] = Field(default_factory=list)
    problem: str | None = None
    root_cause: str | None = None
    fix: str | None = None
    plan: list[dict[str, Any]] = Field(default_factory=list)


class TaskCreate(BaseModel):
    project_id: int
    prompt: str = Field(min_length=3, validation_alias=AliasChoices("prompt", "task"))
    mode: AgentMode = AgentMode.IMPLEMENT
    max_iterations: int | None = Field(default=None, ge=1, le=20)
    problem_description: str | None = None

    model_config = {"populate_by_name": True}

    @field_validator("prompt", mode="before")
    @classmethod
    def _strip_prompt(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("problem_description", mode="before")
    @classmethod
    def _normalize_optional_problem(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str) and value.strip().lower() in {"", "undefined", "null", "none"}:
            return None
        return value


class TaskOut(BaseModel):
    id: int
    project_id: int
    prompt: str
    mode: str
    status: str
    phase: str
    iteration: int
    max_iterations: int
    branch_name: str | None = None
    error: str | None = None
    report: FinalReport | None = None
    problem_description: str | None = None
    plan: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class AgentEventOut(BaseModel):
    id: int
    event_type: str
    message: str
    payload: dict[str, Any] | None = None
    created_at: datetime | None = None
