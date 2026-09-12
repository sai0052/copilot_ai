"""Planning engine: structured JSON plans from the LLM."""

from __future__ import annotations

import json
import re

from collections.abc import Awaitable, Callable
from typing import Any

from app.agent.hints import problem_hint_block
from app.agent.prompts import SYSTEM_PLANNING
from app.llm.client import OpenAICompatibleClient
from app.llm.errors import LLMError
from app.llm.models import ChatMessage
from app.schemas.agent import ImplementationPlan, PlanStep

Progress = Callable[[str, str, dict[str, Any] | None], Awaitable[None] | None]


def _extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


class PlanningEngine:
    def __init__(self, llm: OpenAICompatibleClient) -> None:
        self.llm = llm

    async def create_plan(
        self,
        task: str,
        context: str,
        mode: str,
        on_progress: Progress | None = None,
        cancel_check: Callable[[], bool] | None = None,
        problem_description: str | None = None,
        project_type: str | None = None,
    ) -> ImplementationPlan:
        hint = problem_hint_block(problem_description)
        detected = project_type or "unknown"
        user = (
            f"Mode: {mode}\nTask: {task}\nDetected project type: {detected}\n\n"
            f"{hint}"
            f"Repository context (focused):\n{context[:4000]}\n\n"
            "Produce the implementation or analysis plan JSON.\n"
            "Do not install or introduce Flask, Django, FastAPI, or React unless that stack is already present."
        )
        try:
            response = await self.llm.complete(
                [
                    ChatMessage(role="system", content=SYSTEM_PLANNING),
                    ChatMessage(role="user", content=user),
                ],
                on_progress=on_progress,
                cancel_check=cancel_check,
            )
            data = _extract_json(response.content or "{}")
            steps = [
                PlanStep(
                    index=int(step.get("index", idx + 1)),
                    title=str(step.get("title") or f"Step {idx + 1}"),
                    detail=str(step.get("detail") or ""),
                    status=step.get("status") or "pending",
                )
                for idx, step in enumerate(data.get("steps") or [])
            ]
            if not steps:
                steps = [
                    PlanStep(index=1, title="Inspect repository", detail="Read relevant files"),
                    PlanStep(index=2, title="Implement or analyze", detail=task),
                    PlanStep(index=3, title="Verify", detail="Run tests if implementing"),
                ]
            return ImplementationPlan(
                summary=str(data.get("summary") or task),
                steps=steps,
                relevant_files=list(data.get("relevant_files") or []),
                tests_to_run=list(data.get("tests_to_run") or ["pytest"]),
                risks=list(data.get("risks") or []),
            )
        except LLMError:
            raise
        except Exception:
            return ImplementationPlan(
                summary=task,
                steps=[
                    PlanStep(index=1, title="Inspect repository", detail="Identify relevant files"),
                    PlanStep(index=2, title="Apply changes", detail=task),
                    PlanStep(index=3, title="Run tests", detail="pytest"),
                ],
                tests_to_run=["pytest"],
            )
