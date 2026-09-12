"""Agent orchestrator: scan, plan, execute, report."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.orm import Session

from app.agent.analyzer import FailureAnalyzer
from app.agent.executor import ToolExecutor, mode_system
from app.agent.hints import normalize_problem_description
from app.agent.loop import AgentLoop
from app.agent.plan_progress import PlanTracker
from app.agent.plan_validator import validate_plan
from app.agent.planner import PlanningEngine
from app.agent.prompts import SYSTEM_EXPLAIN, SYSTEM_REVIEW
from app.agent.state import AgentState
from app.api.events import is_cancelled
from app.config import Settings, get_settings
from app.database.models import AgentTask
from app.database.repository import TaskRepository
from app.embeddings.provider import HashEmbeddingProvider, LocalEmbeddingStore, get_embedding_provider
from app.llm.client import OpenAICompatibleClient, get_llm_client
from app.llm.errors import LLMCancelled, LLMError, RateLimitError
from app.repository.context import ContextBuilder, render_context, render_plan_context
from app.repository.scanner import RepositoryScanner
from app.schemas.agent import FinalReport
from app.tools.registry import ToolRegistry
from app.utils import metrics
from app.utils.logging import get_logger, log_event
from app.utils.security import normalize_repo_root

logger = get_logger(__name__)
EventCallback = Callable[[str, str, dict[str, Any] | None], Awaitable[None]]


class AgentOrchestrator:
    def __init__(
        self,
        db: Session,
        settings: Settings | None = None,
        llm: OpenAICompatibleClient | None = None,
    ) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.llm = llm or get_llm_client(self.settings)
        self.tasks = TaskRepository(db)
        self.scanner = RepositoryScanner()

    async def run_task(self, task_row: AgentTask, emit: EventCallback) -> FinalReport:
        metrics.incr("agent.tasks")
        project = task_row.project
        root = normalize_repo_root(project.root_path)
        tools = ToolRegistry(str(root), mode=task_row.mode)
        hint = normalize_problem_description(getattr(task_row, "problem_description", None))
        timeout = float(self.settings.agent_task_timeout_seconds)
        state = AgentState(
            task=task_row.prompt,
            task_id=task_row.id,
            mode=task_row.mode,
            max_iterations=task_row.max_iterations,
            max_tool_rounds=int(self.settings.agent_max_tool_rounds),
            status="running",
            problem_description=hint,
            deadline=time.monotonic() + timeout,
            started_at=time.monotonic(),
        )
        task_row.status = "running"
        self.tasks.save(task_row)
        tracker = PlanTracker()

        async def emit_plan_changes(changes) -> None:
            if not changes:
                return
            state.plan = tracker.snapshot()
            for change in changes:
                await emit(
                    change.event,
                    change.message,
                    {
                        "step_id": change.step_id,
                        "status": change.status,
                        "plan": state.plan,
                    },
                )
            await emit("plan_updated", "Plan updated", {"plan": state.plan})
            task_row.phase = state.phase
            task_row.state_json = state.model_dump_json()
            self.tasks.save(task_row)

        async def tracked_emit(event_type: str, message: str, payload: dict[str, Any] | None = None) -> None:
            if is_cancelled(task_row.id):
                state.cancelled = True
            self._persist_side_effects(task_row.id, event_type, payload or {})
            if event_type in {
                "rate_limit_reached",
                "rate_limit_waiting",
                "llm_retrying",
                "iteration_started",
                "file_modified",
                "plan_created",
                "plan_updated",
            }:
                task_row.iteration = state.iteration
                task_row.phase = state.phase
                task_row.state_json = state.model_dump_json()
                self.tasks.save(task_row)
            await emit(event_type, message, payload)
            if event_type not in {
                "plan_updated",
                "plan_step_started",
                "plan_step_completed",
                "plan_step_failed",
                "plan_step_skipped",
            }:
                await emit_plan_changes(tracker.apply(event_type, state, payload or {}))

        await tracked_emit("agent_started", "Agent started", {"mode": task_row.mode})
        if hint:
            await tracked_emit("problem_description_received", "User problem description received", None)
            await tracked_emit("analyzing_reported_problem", "Analyzing reported problem", None)

        try:
            if self.settings.agent_require_git_branch and tools.git.is_repo():
                branch = tools.git.create_task_branch()
                task_row.branch_name = branch
                self.tasks.save(task_row)
                if branch:
                    await tracked_emit("git_branch", f"Created branch {branch}", {"branch": branch})

            state.phase = "understanding"
            await tracked_emit("repository_scanning", "Scanning repository", None)
            repo_map = self.scanner.scan(root)
            state.project_type = repo_map.project_type
            await tracked_emit(
                "repository_scanned",
                f"Repository scanned ({len(repo_map.files)} files, type={repo_map.project_type})",
                {"file_count": len(repo_map.files), "project_type": repo_map.project_type},
            )

            if self.settings.embeddings_enabled:
                try:
                    provider = get_embedding_provider(
                        self.settings.embeddings_provider, self.settings.embeddings_model
                    )
                    store = LocalEmbeddingStore(root, provider)
                    pairs = []
                    for info in repo_map.files[:80]:
                        path = root / info.path
                        try:
                            pairs.append((info.path, path.read_text(encoding="utf-8", errors="ignore")[:2000]))
                        except OSError:
                            continue
                    if pairs:
                        store.build(pairs)
                        await tracked_emit("embeddings_indexed", f"Indexed {len(pairs)} files for semantic search", None)
                except Exception as exc:  # optional feature
                    logger.warning("embeddings skipped: %s", exc)
                    store = LocalEmbeddingStore(root, HashEmbeddingProvider())
            else:
                store = None

            extra_paths: list[str] = []
            if store:
                extra_paths = [hit["path"] for hit in store.search(task_row.prompt)]
                if hint:
                    extra_paths.extend(hit["path"] for hit in store.search(hint))

            search_query = task_row.prompt if not hint else f"{task_row.prompt}\n{hint}"
            builder = ContextBuilder(root, self.settings)
            bundle = builder.select(search_query, repo_map, extra_paths)
            context = render_context(bundle)
            plan_context = render_plan_context(bundle)
            await tracked_emit("search_completed", "Relevant files identified", {"files": [f["path"] for f in bundle["files"][:12]]})

            state.phase = "planning"
            planner = PlanningEngine(self.llm)
            plan = await planner.create_plan(
                task_row.prompt,
                plan_context,
                task_row.mode,
                on_progress=tracked_emit,
                cancel_check=lambda: bool(state.cancelled or is_cancelled(task_row.id) or state.timed_out()),
                problem_description=hint,
                project_type=repo_map.project_type,
            )
            plan = validate_plan(plan, repo_map.project_type)
            tracker.load(plan.steps)
            state.plan = tracker.snapshot()
            state.root_cause = plan.summary
            await tracked_emit("plan_created", plan.summary, {"plan": state.plan})
            await emit_plan_changes(
                tracker.on_plan_ready(scan_already_done=True, mode=task_row.mode)
            )
            if hint:
                await tracked_emit("root_cause_identified", "Root cause identified", {"summary": plan.summary})
                await tracked_emit("applying_fix", "Applying fix", None)

            executor = ToolExecutor(self.llm, tools)
            analyzer = FailureAnalyzer(self.llm)
            loop = AgentLoop(executor, analyzer, tools)

            assistant_text = ""
            if task_row.mode == "implement" or task_row.mode == "issue":
                assistant_text = await loop.run_implement(state, context, tracked_emit)
            elif task_row.mode == "review":
                state.phase = "reviewing"
                assistant_text = await executor.run(state, context, tracked_emit, extra_system=SYSTEM_REVIEW)
                if state.status not in {"cancelled", "timeout", "limit_reached"}:
                    state.status = "success"
            elif task_row.mode == "explain":
                state.phase = "explaining"
                assistant_text = await executor.run(state, context, tracked_emit, extra_system=SYSTEM_EXPLAIN)
                if state.status not in {"cancelled", "timeout", "limit_reached"}:
                    state.status = "success"
            else:
                assistant_text = await loop.run_implement(state, context, tracked_emit)

            if hint and state.status == "success":
                await tracked_emit("verifying_fix", "Verifying fix", None)

            mapped_preview = _finalize_status(
                state,
                assistant_text,
                int((state.test_results[-1].get("failed") or 0) if state.test_results else 0),
            )
            await emit_plan_changes(tracker.finalize(mapped_preview, state))
            state.plan = tracker.snapshot()
            report = await self._build_report(state, assistant_text, tools)
            mapped = report.status
            state.phase = "completed" if mapped == "SUCCESS" else "failed"
            task_row.iteration = state.iteration
            task_row.phase = state.phase
            task_row.state_json = state.model_dump_json()
            self.tasks.mark_complete(task_row, _db_status(mapped), report.model_dump())
            event = {
                "SUCCESS": "agent_completed",
                "CANCELLED": "agent_cancelled",
                "TIMEOUT": "agent_timeout",
                "LIMIT_REACHED": "agent_limit_reached",
            }.get(mapped, "agent_failed")
            await tracked_emit(event, report.summary, report.model_dump())
            log_event(logger, "agent.finished", task_id=task_row.id, status=task_row.status, iterations=state.iteration)
            return report
        except LLMCancelled:
            if state.timed_out() or state.status == "timeout":
                await emit_plan_changes(tracker.finalize("TIMEOUT", state))
                return await self._fail(task_row, state, "Task stopped — timeout reached", tracked_emit, status="timeout")
            state.cancelled = True
            await emit_plan_changes(tracker.finalize("CANCELLED", state))
            return await self._fail(task_row, state, "Agent cancelled", tracked_emit, status="cancelled")
        except RateLimitError as exc:
            metrics.incr("agent.llm_failures")
            await emit_plan_changes(tracker.finalize("FAILED", state))
            return await self._fail(task_row, state, str(exc), tracked_emit, extra=exc.to_public_dict())
        except LLMError as exc:
            metrics.incr("agent.llm_failures")
            await emit_plan_changes(tracker.finalize("FAILED", state))
            return await self._fail(task_row, state, str(exc), tracked_emit, extra=exc.to_public_dict())
        except Exception as exc:  # noqa: BLE001
            logger.exception("agent crashed")
            await emit_plan_changes(tracker.finalize("FAILED", state))
            return await self._fail(task_row, state, "Agent execution failed.", tracked_emit)

    def _persist_side_effects(self, task_id: int, event_type: str, payload: dict[str, Any]) -> None:
        try:
            if event_type == "file_modified" and payload.get("path"):
                action = "delete" if payload.get("tool") == "delete_file" else "modify"
                self.tasks.add_change(task_id, str(payload["path"]), action, payload.get("diff"))
                self.tasks.add_snapshot(task_id, str(payload["path"]), str(payload.get("diff") or "")[:50000])
            if event_type == "command_completed" and payload.get("command"):
                self.tasks.add_command(
                    task_id,
                    str(payload.get("command")),
                    payload.get("exit_code"),
                    str(payload.get("stdout") or ""),
                    str(payload.get("stderr") or ""),
                    int(payload.get("duration_ms") or 0),
                )
            if event_type == "test_completed":
                self.tasks.add_test_run(
                    task_id,
                    str(payload.get("command") or "pytest"),
                    int(payload.get("passed") or 0),
                    int(payload.get("failed") or 0),
                    int(payload.get("exit_code") or 1),
                    (str(payload.get("stdout") or "") + "\n" + str(payload.get("stderr") or ""))[:20000],
                    int(payload.get("duration_ms") or 0),
                )
        except Exception:
            logger.exception("failed to persist agent side effects")

    async def _fail(
        self,
        task_row: AgentTask,
        state: AgentState,
        error: str,
        emit: EventCallback,
        extra: dict[str, Any] | None = None,
        status: str = "failed",
    ) -> FinalReport:
        state.status = status
        state.phase = "failed"
        report = FinalReport(
            task=state.task,
            status=_status_label(status),
            summary=error,
            files_changed=state.files_modified,
            commands_executed=state.commands_executed,
            iterations_used=state.iteration,
            tool_rounds=state.tool_rounds,
            duration_seconds=round(state.duration_seconds(), 2),
            warnings=state.warnings + [error],
            problem=state.problem_description,
            root_cause=state.root_cause,
            fix=(", ".join(state.files_modified) if state.files_modified else None),
            plan=list(state.plan),
        )
        task_row.error = error
        task_row.iteration = state.iteration
        task_row.phase = state.phase
        task_row.state_json = state.model_dump_json()
        self.tasks.mark_complete(task_row, _db_status(_status_label(status)), report.model_dump())
        payload = report.model_dump()
        if extra:
            payload.update(extra)
        event = {
            "cancelled": "agent_cancelled",
            "timeout": "agent_timeout",
            "limit_reached": "agent_limit_reached",
        }.get(status, "agent_failed")
        message = error
        if extra and extra.get("type") == "rate_limit":
            message = "LLM rate limit exceeded. Please wait and try again."
        await emit(event, message, payload)
        return report

    async def _build_report(self, state: AgentState, assistant_text: str, tools: ToolRegistry) -> FinalReport:
        tests_passed = 0
        tests_failed = 0
        tests_executed = ""
        if state.test_results:
            last = state.test_results[-1]
            tests_passed = int(last.get("passed") or 0)
            tests_failed = int(last.get("failed") or 0)
            tests_executed = str(last.get("command") or "pytest")
        status = _finalize_status(state, assistant_text, tests_failed)
        review_findings = []
        if state.mode in {"review", "explain"}:
            parsed = _maybe_json(assistant_text)
            if "findings" in parsed:
                review_findings = parsed["findings"]
        return FinalReport(
            task=state.task,
            status=status,
            summary=_summary_for(state, assistant_text, status),
            files_changed=list(state.files_modified),
            tests_executed=tests_executed,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            commands_executed=list(state.commands_executed),
            iterations_used=state.iteration,
            tool_rounds=state.tool_rounds,
            duration_seconds=round(state.duration_seconds(), 2),
            decisions=list(state.decisions),
            warnings=list(state.warnings),
            review_findings=review_findings,
            problem=state.problem_description,
            root_cause=state.root_cause,
            fix=(", ".join(state.files_modified) if state.files_modified else None),
            plan=list(state.plan),
        )


def _db_status(mapped: str) -> str:
    return {
        "SUCCESS": "success",
        "FAILED": "failed",
        "CANCELLED": "cancelled",
        "LIMIT_REACHED": "limit_reached",
        "TIMEOUT": "timeout",
        "QUEUED": "queued",
        "RUNNING": "running",
    }.get(mapped, "failed")


def _finalize_status(state: AgentState, assistant_text: str, tests_failed: int) -> str:
    if state.cancelled or state.status == "cancelled" or state.stop_reason == "cancelled":
        return "CANCELLED"
    if state.status == "timeout" or state.stop_reason == "timeout":
        return "TIMEOUT"
    if state.status == "limit_reached" or state.stop_reason in {"tool_round_limit", "iteration_limit"}:
        return "LIMIT_REACHED"
    text = (assistant_text or "").lower()
    if "tool-round limit" in text or text.startswith("stopped after tool-round"):
        return "LIMIT_REACHED"
    if state.status == "failed":
        return "FAILED"
    if state.mode in {"implement", "issue"}:
        last = state.test_results[-1] if state.test_results else None
        if tests_failed > 0:
            return "FAILED"
        if not last or last.get("timed_out"):
            return "FAILED"
        try:
            exit_code = int(last.get("exit_code"))
        except (TypeError, ValueError):
            return "FAILED"
        if exit_code != 0:
            return "FAILED"
        return "SUCCESS"
    if state.status == "success":
        return "SUCCESS"
    return "FAILED"


def _status_label(status: str) -> str:
    mapping = {
        "success": "SUCCESS",
        "failed": "FAILED",
        "cancelled": "CANCELLED",
        "limit_reached": "LIMIT_REACHED",
        "timeout": "TIMEOUT",
        "running": "RUNNING",
        "queued": "QUEUED",
    }
    return mapping.get((status or "").lower(), (status or "FAILED").upper())


def _summary_for(state: AgentState, assistant_text: str, status: str) -> str:
    if status == "LIMIT_REACHED":
        if state.stop_reason == "iteration_limit":
            return "Task stopped — iteration limit reached"
        return "Task stopped — tool-round limit reached"
    if status == "TIMEOUT":
        return "Task stopped — timeout reached"
    if status == "CANCELLED":
        return "Task cancelled"
    text = (assistant_text or "").strip()
    if text.lower().startswith("stopped after tool-round"):
        return "Task stopped — tool-round limit reached"
    return (text or status)[:500]


def _maybe_json(text: str) -> dict:
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
