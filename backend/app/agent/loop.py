"""Autonomous implement → test → diagnose loop."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.agent.analyzer import FailureAnalyzer
from app.agent.executor import ToolExecutor, mode_system
from app.agent.state import AgentState
from app.api.events import is_cancelled
from app.tools.registry import ToolRegistry

EventCallback = Callable[[str, str, dict[str, Any] | None], Awaitable[None]]


class AgentLoop:
    def __init__(
        self,
        executor: ToolExecutor,
        analyzer: FailureAnalyzer,
        tools: ToolRegistry,
    ) -> None:
        self.executor = executor
        self.analyzer = analyzer
        self.tools = tools

    async def run_implement(self, state: AgentState, context: str, emit: EventCallback) -> str:
        last_message = ""
        while state.iteration < state.max_iterations and not state.cancelled:
            if state.task_id and is_cancelled(state.task_id):
                state.cancelled = True
                state.status = "cancelled"
                state.stop_reason = "cancelled"
                return last_message
            if state.timed_out():
                state.status = "timeout"
                state.stop_reason = "timeout"
                await emit("timeout_reached", "Task stopped — timeout reached", None)
                return last_message
            state.iteration += 1
            await emit("iteration_started", f"Starting iteration {state.iteration}", {"iteration": state.iteration})
            state.phase = "implementing"
            tests_before = len(state.test_results)
            last_message = await self.executor.run(state, context, emit, extra_system=mode_system("implement"))
            if state.status in {"cancelled", "timeout", "limit_reached"}:
                return last_message
            state.phase = "testing"
            if len(state.test_results) > tests_before:
                test = state.test_results[-1]
                await emit("test_completed", "Reusing tests already run this iteration", test)
            else:
                await emit("test_started", "Running tests...", None)
                test = self.tools.tests.run_tests()
                state.test_results.append(test)
                state.commands_executed.append(test.get("command") or "pytest")
                await emit(
                    "test_completed",
                    f"Tests finished with exit code {test.get('exit_code')}",
                    test,
                )
            if test.get("exit_code") == 0 and not test.get("timed_out"):
                if state.stop_reason in {"tool_round_limit", "timeout"}:
                    return last_message
                state.status = "success"
                return last_message
            if state.iteration >= state.max_iterations:
                break
            if state.timed_out():
                state.status = "timeout"
                state.stop_reason = "timeout"
                return last_message
            state.phase = "analyzing"
            diff = self.tools.git.diff()
            diagnosis = await self.analyzer.diagnose(
                state.task,
                ((test.get("stdout") or "") + "\n" + (test.get("stderr") or ""))[:1500],
                diff[:2500],
                context[:2000],
                cancel_check=lambda: bool(state.cancelled or is_cancelled(state.task_id) or state.timed_out()),
            )
            state.warnings.append(diagnosis.root_cause)
            context = (
                f"Previous iteration failed tests.\n"
                f"Root cause: {diagnosis.root_cause}\n"
                f"Proposed fix: {diagnosis.proposed_fix}\n"
                f"Affected files: {', '.join(diagnosis.affected_files)}\n"
                "Apply only the proposed fix with tools. Do not resend unrelated files."
            )
            last_message = diagnosis.proposed_fix
        if state.status not in {"success", "cancelled", "timeout", "limit_reached"}:
            state.status = "limit_reached"
            state.stop_reason = "iteration_limit"
            state.warnings.append("Reached iteration limit before tests passed")
            await emit("limit_reached", "Task stopped — iteration limit reached", {"iteration": state.iteration})
        return last_message
