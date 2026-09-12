from __future__ import annotations

import json
import logging

import httpx
import pytest

from app.config import Settings
from app.llm.client import OpenAICompatibleClient
from app.llm.errors import AuthError, ForbiddenError, LLMCancelled, LLMError, RateLimitError
from app.llm.models import ChatMessage

OK = {
    "id": "chatcmpl-test",
    "model": "openai/gpt-oss-120b",
    "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
}


def _settings(**kwargs) -> Settings:
    data = dict(
        llm_api_key="test-key",
        llm_base_url="https://api.groq.com/openai/v1",
        llm_model="openai/gpt-oss-120b",
        llm_max_retries=3,
        llm_retry_base_seconds=5.0,
        llm_retry_jitter=0.0,
        llm_timeout_seconds=5.0,
        llm_max_tokens=128,
        llm_temperature=0.2,
        context_max_tokens=12000,
    )
    data.update(kwargs)
    return Settings.model_construct(**data)


def _client(handler) -> OpenAICompatibleClient:
    client = OpenAICompatibleClient(_settings())
    client._transport = httpx.MockTransport(handler)
    return client


@pytest.mark.asyncio
async def test_successful_llm_request():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("authorization") == "Bearer test-key"
        return httpx.Response(200, json=OK)

    client = _client(handler)
    result = await client.complete([ChatMessage(role="user", content="hi")])
    assert result.content == "ok"
    assert result.raw_model == "openai/gpt-oss-120b"


@pytest.mark.asyncio
async def test_429_then_success_retries_once():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(
                429,
                json={"error": {"message": "Rate limit reached", "type": "tokens", "code": "rate_limit_exceeded"}},
            )
        return httpx.Response(200, json=OK)

    events = []

    async def progress(event, message, payload=None):
        events.append((event, message, payload))

    client = _client(handler)
    result = await client.complete([ChatMessage(role="user", content="hi")], on_progress=progress)
    assert result.content == "ok"
    assert calls["n"] == 2
    assert any(item[0] == "rate_limit_reached" for item in events)
    assert any(item[0] == "llm_retry_succeeded" for item in events)
    assert client._sleeps[0] == 5.0


@pytest.mark.asyncio
async def test_429_three_times_stops():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(429, json={"error": {"message": "Rate limit reached", "code": "rate_limit_exceeded"}})

    client = _client(handler)
    with pytest.raises(RateLimitError) as exc:
        await client.complete([ChatMessage(role="user", content="hi")])
    assert calls["n"] == 3
    public = exc.value.to_public_dict()
    assert public["type"] == "rate_limit"
    assert public["retryable"] is True
    assert "test-key" not in str(exc.value)
    assert "wait and try again" in public["message"].lower()


@pytest.mark.asyncio
async def test_retry_after_header():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "12.3"}, json={"error": {"message": "slow down"}})
        return httpx.Response(200, json=OK)

    client = _client(handler)
    await client.complete([ChatMessage(role="user", content="hi")])
    assert client._sleeps[0] == pytest.approx(12.3)


@pytest.mark.asyncio
async def test_401_not_retried():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(401, json={"error": {"message": "invalid key"}})

    client = _client(handler)
    with pytest.raises(AuthError) as exc:
        await client.complete([ChatMessage(role="user", content="hi")])
    assert calls["n"] == 1
    assert "invalid or expired" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_403_not_retried():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(403, json={"error": {"message": "forbidden"}})

    client = _client(handler)
    with pytest.raises(ForbiddenError) as exc:
        await client.complete([ChatMessage(role="user", content="hi")])
    assert calls["n"] == 1
    assert exc.value.retryable is False
    assert exc.value.status_code == 403
    assert "does not have access" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_408_is_retried_then_fails():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(408, json={"error": {"message": "timeout"}})

    client = _client(handler)
    with pytest.raises(LLMError) as exc:
        await client.complete([ChatMessage(role="user", content="hi")])
    assert calls["n"] == 3
    assert exc.value.status_code == 408
    assert exc.value.retryable is True


@pytest.mark.asyncio
async def test_timeout_exception_is_retried():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.TimeoutException("slow")

    client = _client(handler)
    with pytest.raises(LLMError) as exc:
        await client.complete([ChatMessage(role="user", content="hi")])
    assert calls["n"] == 3
    assert exc.value.status_code == 408


@pytest.mark.asyncio
async def test_404_not_retried():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(404, json={"error": {"message": "model not found"}})

    client = _client(handler)
    with pytest.raises(LLMError) as exc:
        await client.complete([ChatMessage(role="user", content="hi")])
    assert calls["n"] == 1
    assert exc.value.status_code == 404
    assert exc.value.retryable is False
    assert "model was not found" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_500_is_retried():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(500, json={"error": {"message": "upstream"}})
        return httpx.Response(200, json=OK)

    client = _client(handler)
    result = await client.complete([ChatMessage(role="user", content="hi")])
    assert result.content == "ok"
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_cancel_during_backoff_skips_retry():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(429, json={"error": {"message": "rate"}})

    cancelled = {"yes": False}

    async def progress(event, message, payload=None):
        if event == "rate_limit_reached":
            cancelled["yes"] = True

    client = _client(handler)
    with pytest.raises(LLMCancelled):
        await client.complete(
            [ChatMessage(role="user", content="hi")],
            on_progress=progress,
            cancel_check=lambda: cancelled["yes"],
        )
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_error_and_logs_never_include_api_key(caplog):
    caplog.set_level(logging.INFO)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "Rate limit", "code": "rate_limit_exceeded"}})

    client = _client(handler)
    with pytest.raises(RateLimitError) as exc:
        await client.complete([ChatMessage(role="user", content="hi")])
    joined = " ".join(record.getMessage() for record in caplog.records) + str(exc.value) + json.dumps(exc.value.to_public_dict())
    assert "test-key" not in joined
    assert "Bearer" not in joined


@pytest.mark.asyncio
async def test_retry_preserves_request_payload():
    bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content.decode()))
        if len(bodies) == 1:
            return httpx.Response(429, json={"error": {"message": "rate"}})
        return httpx.Response(200, json=OK)

    client = _client(handler)
    await client.complete([ChatMessage(role="user", content="keep this state")])
    assert bodies[0]["messages"] == bodies[1]["messages"]
    assert bodies[0]["model"] == "openai/gpt-oss-120b"
    assert "test-key" not in json.dumps(bodies[0])


@pytest.mark.asyncio
async def test_exponential_backoff_without_retry_after():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(429, json={"error": {"message": "Rate limit reached", "code": "rate_limit_exceeded"}})

    client = _client(handler)
    with pytest.raises(RateLimitError):
        await client.complete([ChatMessage(role="user", content="hi")])
    assert calls["n"] == 3
    assert client._sleeps == [5.0, 10.0]


@pytest.mark.asyncio
async def test_400_not_retried():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(400, json={"error": {"message": "bad request"}})

    client = _client(handler)
    with pytest.raises(LLMError) as exc:
        await client.complete([ChatMessage(role="user", content="hi")])
    assert calls["n"] == 1
    assert exc.value.status_code == 400
    assert exc.value.retryable is False


@pytest.mark.asyncio
async def test_network_error_is_retried():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ConnectError("offline")

    client = _client(handler)
    with pytest.raises(LLMError) as exc:
        await client.complete([ChatMessage(role="user", content="hi")])
    assert calls["n"] == 3
    assert exc.value.error_type == "network"
    assert exc.value.retryable is True
    assert "unable to reach" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_retry_after_from_error_body():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(
                429,
                json={"error": {"message": "Rate limit reached for tokens. Please try again in 8.5s"}},
            )
        return httpx.Response(200, json=OK)

    client = _client(handler)
    await client.complete([ChatMessage(role="user", content="hi")])
    assert client._sleeps[0] == pytest.approx(8.5)

