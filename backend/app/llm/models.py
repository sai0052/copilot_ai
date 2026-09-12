"""LLM data models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


class ToolSpec(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]


class LLMUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LLMResponse(BaseModel):
    content: str = ""
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    usage: LLMUsage = Field(default_factory=LLMUsage)
    raw_model: str = ""
    finish_reason: str = ""
