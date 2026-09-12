"""Track plan-step status from real agent events (not cosmetic SUCCESS mapping)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

PENDING = "PENDING"
RUNNING = "RUNNING"
COMPLETED = "COMPLETED"
FAILED = "FAILED"
SKIPPED = "SKIPPED"
CANCELLED = "CANCELLED"

_STATUS_ALIASES = {
    "pending": PENDING,
    "in_progress": RUNNING,
    "running": RUNNING,
    "done": COMPLETED,
    "complete": COMPLETED,
    "completed": COMPLETED,
    "failed": FAILED,
    "fail": FAILED,
    "skipped": SKIPPED,
    "skip": SKIPPED,
    "cancelled": CANCELLED,
    "canceled": CANCELLED,
}


def normalize_status(value: str | None) -> str:
    raw = (value or PENDING).strip()
    return _STATUS_ALIASES.get(raw.lower(), raw.upper() if raw else PENDING)


def classify_step(title: str, detail: str = "") -> str:
    text = f"{title} {detail}".lower()
    if any(token in text for token in ("commit", "git push", "push changes")):
        return "commit"
    if any(token in text for token in ("run test", "run tests", "test suite", "pytest", "verify", "run the complete test")):
        if any(token in text for token in ("add test", "update test", "write test", "create test", "fix test", "test syntax")):
            return "implement"
        return "test"
    if any(token in text for token in ("inspect", "scan", "identify", "relevant file", "understand", "read repo", "repository")):
        return "inspect"
    if "review" in text or "audit" in text:
        return "review"
    if "explain" in text:
        return "explain"
    return "implement"


@dataclass
class PlanStepState:
    id: int
    title: str
    detail: str
    status: str = PENDING
    kind: str = "implement"

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "index": self.id,
            "title": self.title,
            "detail": self.detail,
            "status": self.status,
            "kind": self.kind,
        }


@dataclass
class PlanTransition:
    event: str
    message: str
    step_id: int
    status: str


@dataclass
class PlanTracker:
    steps: list[PlanStepState] = field(default_factory=list)
    _seen: set[tuple[int, str]] = field(default_factory=set)

    def load(self, raw_steps: list[Any]) -> None:
        self.steps = []
        self._seen.clear()
        for idx, item in enumerate(raw_steps or [], start=1):
            if hasattr(item, "model_dump"):
                data = item.model_dump()
            elif isinstance(item, dict):
                data = item
            else:
                data = {"title": str(item)}
            title = str(data.get("title") or f"Step {idx}")
            detail = str(data.get("detail") or "")
            step_id = int(data.get("id") or data.get("index") or idx)
            self.steps.append(
                PlanStepState(
                    id=step_id,
                    title=title,
                    detail=detail,
                    status=normalize_status(str(data.get("status") or PENDING)),
                    kind=classify_step(title, detail),
                )
            )

    def snapshot(self) -> list[dict[str, Any]]:
        return [step.as_dict() for step in self.steps]

    def on_plan_ready(self, *, scan_already_done: bool, mode: str) -> list[PlanTransition]:
        changes: list[PlanTransition] = []
        if scan_already_done:
            changes.extend(self._set_kind("inspect", COMPLETED, "plan_step_completed", "completed"))
        if mode in {"review", "explain"}:
            changes.extend(self._start_kind(mode if mode != "issue" else "implement"))
        else:
            changes.extend(self._start_kind("implement") or self._start_next_pending())
        return changes

    def apply(self, event_type: str, state: Any, payload: dict[str, Any] | None = None) -> list[PlanTransition]:
        payload = payload or {}
        if event_type in {"plan_updated", "plan_step_started", "plan_step_completed", "plan_step_failed", "plan_step_skipped"}:
            return []
        if event_type in {"repository_scanned", "search_completed", "file_read"}:
            changes = self._set_kind("inspect", COMPLETED, "plan_step_completed", "completed")
            if not self._running():
                changes.extend(self._start_kind("implement") or self._start_next_pending())
            return changes
        if event_type in {"file_modified", "applying_fix"}:
            changes = self._set_kind("inspect", COMPLETED, "plan_step_completed", "completed")
            changes.extend(self._start_kind("implement"))
            return changes
        if event_type == "test_started":
            changes = self._complete_running_of("implement")
            if getattr(state, "files_modified", None):
                changes.extend(self._set_kind("implement", COMPLETED, "plan_step_completed", "completed"))
            changes.extend(self._start_kind("test") or self._start_next_pending())
            return changes
        if event_type == "test_completed":
            exit_code = payload.get("exit_code")
            try:
                ok = int(exit_code) == 0 and not payload.get("timed_out")
            except (TypeError, ValueError):
                ok = False
            if ok:
                changes = self._complete_running_of("implement")
                changes.extend(self._set_kind("test", COMPLETED, "plan_step_completed", "completed"))
                return changes
            return self._fail_running()
        if event_type in {"agent_completed"}:
            return self.finalize("SUCCESS", state)
        if event_type == "agent_cancelled":
            return self.finalize("CANCELLED", state)
        if event_type == "agent_timeout":
            return self.finalize("TIMEOUT", state)
        if event_type in {"agent_limit_reached", "limit_reached"}:
            return self.finalize("LIMIT_REACHED", state)
        if event_type == "agent_failed":
            return self.finalize("FAILED", state)
        if event_type in {"timeout_reached"}:
            return self.finalize("TIMEOUT", state)
        return []

    def finalize(self, outcome: str, state: Any) -> list[PlanTransition]:
        changes: list[PlanTransition] = []
        committed = any("commit" in str(cmd).lower() for cmd in getattr(state, "commands_executed", []) or [])
        files_changed = bool(getattr(state, "files_modified", None))
        tests_ok = False
        results = getattr(state, "test_results", None) or []
        if results:
            last = results[-1]
            try:
                tests_ok = int(last.get("exit_code")) == 0 and not last.get("timed_out")
            except (TypeError, ValueError):
                tests_ok = False

        if outcome == "SUCCESS":
            changes.extend(self._set_kind("inspect", COMPLETED, "plan_step_completed", "completed"))
            if files_changed or tests_ok:
                changes.extend(self._set_kind("implement", COMPLETED, "plan_step_completed", "completed"))
            if tests_ok:
                changes.extend(self._set_kind("test", COMPLETED, "plan_step_completed", "completed"))
            changes.extend(self._complete_running())
            if not committed:
                for step in self.steps:
                    if step.kind == "commit":
                        step.detail = "SKIPPED — Optional commit not requested"
                changes.extend(self._set_kind("commit", SKIPPED, "plan_step_skipped", "skipped"))
            changes.extend(self._skip_pending())
            return changes

        if outcome == "CANCELLED":
            changes.extend(self._set_running(CANCELLED, "plan_step_failed", "cancelled"))
            changes.extend(self._skip_pending())
            return changes

        changes.extend(self._fail_running())
        if outcome in {"TIMEOUT", "LIMIT_REACHED", "FAILED"}:
            return changes
        return changes

    def _running(self) -> list[PlanStepState]:
        return [step for step in self.steps if step.status == RUNNING]

    def _set_running(self, status: str, event: str, verb: str) -> list[PlanTransition]:
        changes: list[PlanTransition] = []
        for step in self._running():
            changes.extend(self._set_step(step, status, event, verb))
        return changes

    def _fail_running(self) -> list[PlanTransition]:
        return self._set_running(FAILED, "plan_step_failed", "failed")

    def _complete_running(self) -> list[PlanTransition]:
        return self._set_running(COMPLETED, "plan_step_completed", "completed")

    def _complete_running_of(self, kind: str) -> list[PlanTransition]:
        changes: list[PlanTransition] = []
        for step in self.steps:
            if step.kind == kind and step.status == RUNNING:
                changes.extend(self._set_step(step, COMPLETED, "plan_step_completed", "completed"))
        return changes

    def _skip_pending(self) -> list[PlanTransition]:
        changes: list[PlanTransition] = []
        for step in self.steps:
            if step.status == PENDING:
                changes.extend(self._set_step(step, SKIPPED, "plan_step_skipped", "skipped"))
        return changes

    def _start_kind(self, kind: str) -> list[PlanTransition]:
        changes: list[PlanTransition] = []
        targets = [step for step in self.steps if step.kind == kind and step.status == PENDING]
        if not targets:
            return changes
        if self._running():
            return changes
        changes.extend(self._set_step(targets[0], RUNNING, "plan_step_started", "started"))
        return changes

    def _start_next_pending(self) -> list[PlanTransition]:
        if self._running():
            return []
        for step in self.steps:
            if step.status == PENDING:
                return self._set_step(step, RUNNING, "plan_step_started", "started")
        return []

    def _set_kind(self, kind: str, status: str, event: str, verb: str) -> list[PlanTransition]:
        changes: list[PlanTransition] = []
        allowed_from = {PENDING, RUNNING} if status != RUNNING else {PENDING}
        if status == COMPLETED:
            allowed_from = {PENDING, RUNNING}
        if status == SKIPPED:
            allowed_from = {PENDING, RUNNING}
        for step in self.steps:
            if step.kind == kind and step.status in allowed_from and step.status != status:
                changes.extend(self._set_step(step, status, event, verb))
        return changes

    def _set_step(self, step: PlanStepState, status: str, event: str, verb: str) -> list[PlanTransition]:
        key = (step.id, status)
        if step.status == status or key in self._seen:
            return []
        self._seen.add(key)
        step.status = status
        return [
            PlanTransition(
                event=event,
                message=f"Step {step.id} {verb}: {step.title}",
                step_id=step.id,
                status=status,
            )
        ]
