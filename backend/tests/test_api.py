from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def test_health(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "codepilot-ai"
    assert "version" in body
    assert body["model"] == "openai/gpt-oss-120b"
    assert "llm_configured" in body
    assert "LLM_API_KEY" not in response.text
    assert "your_api_key_here" not in response.text


def test_metrics(client: TestClient):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "counters" in response.json()


def test_api_routes_registered(client: TestClient):
    spec = client.get("/openapi.json")
    assert spec.status_code == 200
    paths = spec.json()["paths"]
    for path in (
        "/health",
        "/api/projects",
        "/api/projects/{project_id}/scan",
        "/api/projects/{project_id}/files",
        "/api/projects/{project_id}/file",
        "/api/projects/{project_id}/diff",
        "/api/agent/tasks",
        "/api/agent/tasks/{task_id}",
        "/api/agent/tasks/{task_id}/events",
        "/api/agent/tasks/{task_id}/cancel",
        "/api/projects/import",
        "/api/projects/browse",
    ):
        assert path in paths, path


def test_register_scan_and_list_files(client: TestClient, tmp_path: Path):
    (tmp_path / "requirements.txt").write_text("fastapi\n", encoding="utf-8")
    (tmp_path / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8")
    created = client.post("/api/projects", json={"root_path": str(tmp_path), "name": "demo"})
    assert created.status_code == 200
    project_id = created.json()["id"]
    assert created.json()["project_type"] == "fastapi"
    scanned = client.post(f"/api/projects/{project_id}/scan")
    assert scanned.status_code == 200
    assert scanned.json()["file_count"] >= 2
    assert "main.py" in scanned.json()["tree"]
    files = client.get(f"/api/projects/{project_id}/files")
    assert files.status_code == 200
    listed = client.get("/api/projects")
    assert listed.status_code == 200
    assert any(item["id"] == project_id for item in listed.json())


def test_invalid_repository_path(client: TestClient, tmp_path: Path):
    missing = client.post("/api/projects", json={"root_path": str(tmp_path / "nope")})
    assert missing.status_code == 404
    assert "does not exist" in missing.json()["detail"].lower()


def test_agent_task_requires_llm(client: TestClient, tmp_path: Path, monkeypatch):
    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")
    created = client.post("/api/projects", json={"root_path": str(tmp_path)})
    project_id = created.json()["id"]

    class FakeSettings:
        agent_max_iterations = 5
        llm_is_configured = False

    monkeypatch.setattr("app.api.routes.agent.get_settings", lambda: FakeSettings())
    response = client.post(
        "/api/agent/tasks",
        json={"project_id": project_id, "prompt": "Add a /health endpoint.", "mode": "implement"},
    )
    assert response.status_code == 400
    assert "LLM unavailable" in response.json()["detail"]
    assert "sk-" not in response.text.lower()


def test_agent_task_creation_when_llm_configured(client: TestClient, tmp_path: Path, monkeypatch):
    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")
    created = client.post("/api/projects", json={"root_path": str(tmp_path)})
    project_id = created.json()["id"]

    class FakeSettings:
        agent_max_iterations = 2
        llm_is_configured = True

    async def fake_run(task_id: int) -> None:
        return None

    monkeypatch.setattr("app.api.routes.agent.get_settings", lambda: FakeSettings())
    monkeypatch.setattr("app.api.routes.agent._run", fake_run)
    response = client.post(
        "/api/agent/tasks",
        json={"project_id": project_id, "prompt": "Add a /health endpoint.", "mode": "implement"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == project_id
    assert body["status"] in {"queued", "running"}
    fetched = client.get(f"/api/agent/tasks/{body['id']}")
    assert fetched.status_code == 200
