"""Tool-calling executor for implementation, review, and explain modes."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from app.agent.hints import problem_hint_block
from app.agent.prompts import SYSTEM_AGENT, SYSTEM_EXPLAIN, SYSTEM_IMPLEMENT, SYSTEM_REVIEW
from app.agent.state import AgentState
from app.api.events import is_cancelled
from app.llm.client import OpenAICompatibleClient
from app.llm.errors import LLMCancelled, LLMError
from app.llm.models import ChatMessage
from app.repository.context import estimate_tokens
from app.tools.registry import ToolRegistry
from app.utils.logging import get_logger

logger = get_logger(__name__)

EventCallback = Callable[[str, str, dict[str, Any] | None], Awaitable[None]]

TOOL_RESULT_CHARS = 1800


class ToolExecutor:
    def __init__(self, llm: OpenAICompatibleClient, tools: ToolRegistry) -> None:
        self.llm = llm
        self.tools = tools

    async def run(
        self,
        state: AgentState,
        context: str,
        emit: EventCallback,
        extra_system: str = "",
    ) -> str:
        system = (
            SYSTEM_AGENT
            + f"\nDetected project type: {state.project_type}. Do not introduce a different framework.\n"
            + extra_system
        )
        settings = getattr(self.llm, "settings", None)
        budget = max(1600, int(getattr(settings, "context_max_tokens", 8000) * 0.35))
        max_rounds = int(state.max_tool_rounds or getattr(settings, "agent_max_tool_rounds", 10) or 10)
        focused = _trim_to_tokens(context, budget)
        hint = problem_hint_block(state.problem_description)
        messages: list[ChatMessage] = [
            ChatMessage(role="system", content=system),
            ChatMessage(
                role="user",
                content=(
                    f"Task: {state.task}\nMode: {state.mode}\nIteration: {state.iteration}\n"
                    f"Project type: {state.project_type}\n\n"
                    f"{hint}"
                    f"Focused repository context (use tools for anything missing):\n{focused}"
                ),
            ),
        ]
        last_text = ""
        seen_tool_fingerprint: set[str] = set()
        for round_idx in range(max_rounds):
            if state.cancelled or is_cancelled(state.task_id):
                state.cancelled = True
                state.status = "cancelled"
                state.stop_reason = "cancelled"
                return "Cancelled"
            if state.timed_out():
                state.status = "timeout"
                state.stop_reason = "timeout"
                await emit("timeout_reached", "Task stopped — timeout reached", None)
                return "Task stopped — timeout reached"
            state.tool_rounds += 1
            try:
                response = await self.llm.complete(
                    messages,
                    tools=self.tools.specs(),
                    on_progress=emit,
                    cancel_check=lambda: bool(state.cancelled or is_cancelled(state.task_id) or state.timed_out()),
                )
            except LLMCancelled:
                if state.timed_out():
                    state.status = "timeout"
                    state.stop_reason = "timeout"
                    await emit("timeout_reached", "Task stopped — timeout reached", None)
                    return "Task stopped — timeout reached"
                state.cancelled = True
                state.status = "cancelled"
                state.stop_reason = "cancelled"
                await emit("agent_cancelled", "Agent cancelled during LLM wait", None)
                return "Cancelled"
            except LLMError:
                raise
            if response.tool_calls:
                messages.append(
                    ChatMessage(
                        role="assistant",
                        content=response.content or "",
                        tool_calls=response.tool_calls,
                    )
                )
                for call in response.tool_calls:
                    if state.cancelled or is_cancelled(state.task_id):
                        state.cancelled = True
                        state.status = "cancelled"
                        return "Cancelled"
                    fn = call.get("function") or {}
                    name = fn.get("name") or "unknown"
                    raw_args = fn.get("arguments") or "{}"
                    try:
                        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    except json.JSONDecodeError:
                        args = {}
                    fingerprint = f"{name}:{json.dumps(args, sort_keys=True)[:500]}"
                    if fingerprint in seen_tool_fingerprint and name in {"read_file", "list_files", "search_code"}:
                        messages.append(
                            ChatMessage(
                                role="tool",
                                tool_call_id=call.get("id") or name,
                                name=name,
                                content=json.dumps({"ok": True, "result": "Already retrieved this turn; do not repeat."}),
                            )
                        )
                        continue
                    seen_tool_fingerprint.add(fingerprint)
                    event_name = {
                        "read_file": "file_read",
                        "write_file": "file_modified",
                        "patch_file": "file_modified",
                        "delete_file": "file_modified",
                        "run_command": "command_started",
                        "run_tests": "test_started",
                    }.get(name, "tool_started")
                    await emit(event_name, f"Using tool {name}", {"tool": name, "args": _safe_args(name, args)})
                    result = self.tools.execute(name, args)
                    self._record(state, name, args, result)
                    done_name = {
                        "run_command": "command_completed",
                        "run_tests": "test_completed",
                    }.get(name, "tool_completed")
                    payload = {"tool": name, "ok": result.get("ok"), "path": args.get("path")}
                    inner = result.get("result") if isinstance(result.get("result"), dict) else {}
                    if inner:
                        payload.update(
                            {
                                "diff": inner.get("diff"),
                                "command": inner.get("command") or args.get("command"),
                                "exit_code": inner.get("exit_code"),
                                "stdout": (inner.get("stdout") or "")[:2000],
                                "stderr": (inner.get("stderr") or "")[:2000],
                                "duration_ms": inner.get("duration_ms"),
                                "passed": inner.get("passed"),
                                "failed": inner.get("failed"),
                            }
                        )
                    await emit(done_name, f"Finished {name}", payload)
                    compact = json.dumps(result)[:TOOL_RESULT_CHARS]
                    messages.append(
                        ChatMessage(
                            role="tool",
                            tool_call_id=call.get("id") or name,
                            name=name,
                            content=compact,
                        )
                    )
                    if name == "run_tests":
                        inner_result = result.get("result") if isinstance(result.get("result"), dict) else {}
                        try:
                            tests_ok = int(inner_result.get("exit_code")) == 0 and not inner_result.get("timed_out")
                        except (TypeError, ValueError):
                            tests_ok = False
                        if tests_ok:
                            return last_text or "Tests passed. Requested change is complete."
                messages[:] = _compact_history(messages)
                continue
            last_text = response.content or last_text
            if last_text:
                return last_text
            if round_idx == 0:
                messages.append(
                    ChatMessage(
                        role="user",
                        content="Continue using tools if needed, then summarize what you did.",
                    )
                )
        state.status = "limit_reached"
        state.stop_reason = "tool_round_limit"
        await emit("limit_reached", "Task stopped — tool-round limit reached", {"tool_rounds": state.tool_rounds})
        return "Task stopped — tool-round limit reached"

    def _record(self, state: AgentState, name: str, args: dict[str, Any], result: dict[str, Any]) -> None:
        if name == "read_file" and args.get("path"):
            path = str(args["path"])
            if path not in state.files_inspected:
                state.files_inspected.append(path)
        if name in {"write_file", "patch_file", "delete_file"} and args.get("path"):
            path = str(args["path"])
            if path not in state.files_modified:
                state.files_modified.append(path)
        if name == "run_command":
            state.commands_executed.append(str(args.get("command")))
        if name == "run_tests":
            payload = result.get("result") or {}
            state.commands_executed.append(str(payload.get("command") or "pytest"))
            state.test_results.append(payload)


def _compact_history(messages: list[ChatMessage]) -> list[ChatMessage]:
    if len(messages) <= 12:
        return messages
    head = messages[:2]
    tail = messages[-8:]
    return head + tail


def _trim_to_tokens(text: str, budget: int) -> str:
    if estimate_tokens(text) <= budget:
        return text
    return text[: max(500, budget * 4)] + "\n... [context trimmed]"


def _safe_args(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name in {"write_file", "patch_file"}:
        return {key: (value[:200] if isinstance(value, str) else value) for key, value in args.items()}
    return args


def mode_system(mode: str) -> str:
    if mode == "review":
        return SYSTEM_REVIEW
    if mode == "explain":
        return SYSTEM_EXPLAIN
    return SYSTEM_IMPLEMENT
