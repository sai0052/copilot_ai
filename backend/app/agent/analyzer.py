"""Failure analysis from test output and recent diffs."""

from __future__ import annotations

import json
import re
from collections.abc import Callable

from app.agent.prompts import SYSTEM_FAILURE
from app.llm.client import OpenAICompatibleClient
from app.llm.errors import LLMError
from app.llm.models import ChatMessage
from app.schemas.agent import FailureDiagnosis


class FailureAnalyzer:
    def __init__(self, llm: OpenAICompatibleClient) -> None:
        self.llm = llm

    async def diagnose(
        self,
        task: str,
        test_output: str,
        recent_diff: str,
        relevant_source: str,
        cancel_check: Callable[[], bool] | None = None,
    ) -> FailureDiagnosis:
        prompt = (
            f"Task: {task}\n\nTest/command output:\n{test_output[:1500]}\n\n"
            f"Recent diff:\n{recent_diff[:2000]}\n\nRelevant source:\n{relevant_source[:2000]}"
        )
        try:
            response = await self.llm.complete(
                [
                    ChatMessage(role="system", content=SYSTEM_FAILURE),
                    ChatMessage(role="user", content=prompt),
                ],
                cancel_check=cancel_check,
            )
            data = _json(response.content or "{}")
            return FailureDiagnosis(
                root_cause=str(data.get("root_cause") or "Unknown failure"),
                affected_files=list(data.get("affected_files") or []),
                proposed_fix=str(data.get("proposed_fix") or "Inspect failing tests and recent edits"),
                confidence=float(data.get("confidence") or 0.4),
            )
        except LLMError:
            raise
        except Exception:
            return FailureDiagnosis(
                root_cause="Could not parse failure analysis from the model",
                affected_files=[],
                proposed_fix="Re-read failing tests and the files changed in this task",
                confidence=0.2,
            )


def _json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        return json.loads(match.group(0)) if match else {}
