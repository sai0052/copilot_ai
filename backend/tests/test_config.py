from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.llm.client import OpenAICompatibleClient
from app.main import create_app


def test_settings_read_llm_model_from_env_file(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    env_path = tmp_path / ".env"
    env_path.write_text(
        "LLM_BASE_URL=https://api.groq.com/openai/v1\n"
        "LLM_MODEL=openai/gpt-oss-120b\n"
        "LLM_API_KEY=\n",
        encoding="utf-8",
    )
    settings = Settings(_env_file=str(env_path))
    assert settings.llm_model == "openai/gpt-oss-120b"
    assert settings.llm_base_url == "https://api.groq.com/openai/v1"


def test_settings_env_var_overrides_file(tmp_path: Path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("LLM_MODEL=from-file\n", encoding="utf-8")
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-oss-120b")
    settings = Settings(_env_file=str(env_path))
    assert settings.llm_model == "openai/gpt-oss-120b"


def test_health_reports_configured_model_not_key(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    env_path = tmp_path / ".env"
    env_path.write_text(
        "LLM_BASE_URL=https://api.groq.com/openai/v1\nLLM_MODEL=openai/gpt-oss-120b\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("app.config.env_files", lambda: (str(env_path),))
    get_settings.cache_clear()
    app = create_app()
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "openai/gpt-oss-120b"
    assert body["llm_base_url"] == "https://api.groq.com/openai/v1"
    assert "LLM_API_KEY" not in response.text
    assert "api_key" not in response.text.lower()
    get_settings.cache_clear()


def test_llm_client_uses_configured_model():
    settings = Settings.model_construct(
        llm_api_key="",
        llm_base_url="https://api.groq.com/openai/v1",
        llm_model="openai/gpt-oss-120b",
        llm_temperature=0.2,
        llm_max_tokens=128,
    )
    client = OpenAICompatibleClient(settings)
    payload = client._payload(messages=[], tools=None, temperature=None, response_format=None)
    assert payload["model"] == "openai/gpt-oss-120b"
