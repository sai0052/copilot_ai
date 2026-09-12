"""Provider-independent LLM client interface."""

from __future__ import annotations

from typing import Protocol

from app.llm.models import ChatMessage, LLMResponse, ToolSpec


class LLMProvider(Protocol):
    async def complete(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
        temperature: float | None = None,
        response_format: dict[str, str] | None = None,
    ) -> LLMResponse:
        ...
