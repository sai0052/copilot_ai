"""OpenAI-compatible LLM client (Groq). All agent LLM calls share this retry handler."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.llm.errors import AuthError, ForbiddenError, LLMCancelled, LLMError, ModelNotFoundError, RateLimitError
from app.llm.models import ChatMessage, LLMResponse, LLMUsage, ToolSpec
from app.llm.rate_limit import compute_wait_seconds, public_wait_label

logger = logging.getLogger("codepilot.llm")

ProgressCallback = Callable[[str, str, dict[str, Any] | None], Any]
CancelCheck = Callable[[], bool]

RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


class OpenAICompatibleClient:
    def __init__(self, settings: Settings | None = None, *, transport: httpx.BaseTransport | None = None) -> None:
        self.settings = settings or get_settings()
        self._transport = transport
        self._sleeps: list[float] = []

    def _client(self) -> httpx.AsyncClient:
        headers = {"Content-Type": "application/json"}
        if self.settings.llm_api_key:
            headers["Authorization"] = f"Bearer {self.settings.llm_api_key}"
        timeout = httpx.Timeout(self.settings.llm_timeout_seconds)
        kwargs: dict[str, Any] = {"timeout": timeout, "headers": headers}
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.AsyncClient(**kwargs)

    def _payload(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
        temperature: float | None = None,
        response_format: dict[str, str] | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": [_serialize_message(message) for message in messages],
            "temperature": self.settings.llm_temperature if temperature is None else temperature,
            "max_tokens": max_tokens or self.settings.llm_max_tokens,
        }
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": spec.name,
                        "description": spec.description,
                        "parameters": spec.parameters,
                    },
                }
                for spec in tools
            ]
            payload["tool_choice"] = "auto"
        if response_format:
            payload["response_format"] = response_format
        return payload

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[ToolSpec] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, str] | None = None,
        on_progress: ProgressCallback | None = None,
        cancel_check: CancelCheck | None = None,
        is_cancelled: CancelCheck | None = None,
    ) -> LLMResponse:
        cancelled = cancel_check or is_cancelled
        payload = self._payload(messages, tools=tools, temperature=temperature, response_format=response_format, max_tokens=max_tokens)
        last_error: Exception | None = None
        attempts = max(1, int(self.settings.llm_max_retries))
        for attempt in range(1, attempts + 1):
            self._raise_if_cancelled(cancelled)
            try:
                data = await self._post(payload)
                if attempt > 1:
                    await self._progress(
                        on_progress,
                        "llm_retry_succeeded",
                        "LLM request recovered",
                        {"attempt": attempt, "max_attempts": attempts},
                    )
                return self._parse(data)
            except LLMCancelled:
                raise
            except LLMError as exc:
                last_error = exc
                if not exc.retryable or attempt >= attempts:
                    if isinstance(exc, RateLimitError) and attempt >= attempts:
                        await self._progress(
                            on_progress,
                            "rate_limit_exhausted",
                            "LLM rate limit exceeded. Please wait and try again.",
                            {"attempt": attempt, "max_attempts": attempts},
                        )
                    raise
                wait_s = compute_wait_seconds(
                    retry_after=getattr(exc, "retry_after", None),
                    body=getattr(exc, "body", "") or "",
                    retry_index=attempt - 1,
                    base_seconds=float(self.settings.llm_retry_base_seconds),
                    jitter=0.0 if self._transport is not None else float(getattr(self.settings, "llm_retry_jitter", 0.0)),
                )
                if exc.status_code == 429 or exc.error_type == "rate_limit":
                    await self._progress(
                        on_progress,
                        "rate_limit_reached",
                        "Groq rate limit reached. CodePilot is waiting before retrying.",
                        {"attempt": attempt, "wait_seconds": wait_s},
                    )
                    await self._progress(
                        on_progress,
                        "rate_limit_waiting",
                        public_wait_label(wait_s),
                        {"attempt": attempt, "wait_seconds": wait_s},
                    )
                else:
                    await self._progress(
                        on_progress,
                        "llm_retry_waiting",
                        public_wait_label(wait_s),
                        {"attempt": attempt, "wait_seconds": wait_s, "status_code": exc.status_code},
                    )
                await self._sleep(wait_s, cancelled)
                await self._progress(
                    on_progress,
                    "llm_retrying",
                    f"Retrying LLM request (attempt {attempt + 1}/{attempts})",
                    {"attempt": attempt + 1, "max_attempts": attempts},
                )
        raise last_error or LLMError("LLM request failed")

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.settings.llm_base_url.rstrip('/')}/chat/completions"
        async with self._client() as client:
            try:
                response = await client.post(url, json=payload)
            except httpx.TimeoutException as exc:
                raise LLMError("LLM request timed out.", status_code=408, error_type="timeout", retryable=True) from exc
            except httpx.HTTPError as exc:
                raise LLMError("Unable to reach the LLM provider.", error_type="network", retryable=True) from exc
        text = response.text or ""
        retry_after = response.headers.get("Retry-After") or response.headers.get("retry-after")
        if response.status_code == 429:
            raise RateLimitError(retry_after=retry_after, body=text[:4000])
        if response.status_code == 401:
            raise AuthError()
        if response.status_code == 403:
            raise ForbiddenError()
        if response.status_code == 404:
            raise ModelNotFoundError()
        if response.status_code == 400:
            raise LLMError("Invalid LLM request.", status_code=400, error_type="bad_request", retryable=False)
        if response.status_code in RETRYABLE_STATUS:
            err = LLMError(
                "The LLM provider is temporarily unavailable.",
                status_code=response.status_code,
                error_type="provider_unavailable",
                retryable=True,
            )
            err.retry_after = retry_after
            err.body = text[:4000]
            raise err
        if response.status_code >= 400:
            raise LLMError(
                "The LLM provider rejected the request.",
                status_code=response.status_code,
                error_type="provider_error",
                retryable=False,
            )
        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise LLMError("LLM returned an invalid response.", error_type="invalid_response") from exc
        logger.info("llm request ok model=%s", self.settings.llm_model)
        return data

    def _parse(self, data: dict[str, Any]) -> LLMResponse:
        choices = data.get("choices") or []
        if not choices:
            raise LLMError("LLM returned no choices")
        message = choices[0].get("message") or {}
        usage = data.get("usage") or {}
        return LLMResponse(
            content=message.get("content") or "",
            tool_calls=list(message.get("tool_calls") or []),
            finish_reason=str(choices[0].get("finish_reason") or ""),
            raw_model=str(data.get("model") or self.settings.llm_model),
            usage=LLMUsage(
                prompt_tokens=int(usage.get("prompt_tokens") or 0),
                completion_tokens=int(usage.get("completion_tokens") or 0),
                total_tokens=int(usage.get("total_tokens") or 0),
            ),
        )

    async def _sleep(self, seconds: float, is_cancelled: CancelCheck | None) -> None:
        self._sleeps.append(seconds)
        self._raise_if_cancelled(is_cancelled)
        if seconds <= 0:
            return
        if self._transport is not None:
            await asyncio.sleep(0)
            self._raise_if_cancelled(is_cancelled)
            return
        elapsed = 0.0
        step = 0.25
        while elapsed < seconds:
            self._raise_if_cancelled(is_cancelled)
            chunk = min(step, seconds - elapsed)
            await asyncio.sleep(chunk)
            elapsed += chunk

    def _raise_if_cancelled(self, is_cancelled: CancelCheck | None) -> None:
        if is_cancelled and is_cancelled():
            raise LLMCancelled()

    async def _progress(
        self,
        cb: ProgressCallback | None,
        event: str,
        message: str,
        payload: dict[str, Any] | None,
    ) -> None:
        if not cb:
            return
        result = cb(event, message, payload)
        if asyncio.iscoroutine(result):
            await result


def _serialize_message(message: ChatMessage) -> dict[str, Any]:
    item: dict[str, Any] = {"role": message.role, "content": message.content}
    if message.tool_call_id:
        item["tool_call_id"] = message.tool_call_id
    if message.name:
        item["name"] = message.name
    if message.tool_calls:
        item["tool_calls"] = message.tool_calls
    return item


_client: OpenAICompatibleClient | None = None


def get_llm_client(settings: Settings | None = None) -> OpenAICompatibleClient:
    global _client
    if settings is not None:
        return OpenAICompatibleClient(settings)
    if _client is None:
        _client = OpenAICompatibleClient()
    return _client
