from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def _project(client: TestClient, tmp_path: Path) -> int:
    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")
    return client.post("/api/projects", json={"root_path": str(tmp_path)}).json()["id"]


def _enable_llm(monkeypatch) -> None:
    class FakeSettings:
        agent_max_iterations = 2
        llm_is_configured = True

    async def fake_run(task_id: int) -> None:
        return None

    monkeypatch.setattr("app.api.routes.agent.get_settings", lambda: FakeSettings())
    monkeypatch.setattr("app.api.routes.agent._run", fake_run)


def test_empty_prompt_rejected(client: TestClient, tmp_path: Path, monkeypatch):
    _enable_llm(monkeypatch)
    project_id = _project(client, tmp_path)
    response = client.post("/api/agent/tasks", json={"project_id": project_id, "prompt": "", "mode": "implement"})
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "validation_error"
    assert body["field"] == "prompt"
    assert "at least 3 characters" in body["message"]
    assert "Traceback" not in response.text


def test_whitespace_prompt_rejected(client: TestClient, tmp_path: Path, monkeypatch):
    _enable_llm(monkeypatch)
    project_id = _project(client, tmp_path)
    response = client.post("/api/agent/tasks", json={"project_id": project_id, "prompt": "   ", "mode": "implement"})
    assert response.status_code == 422
    assert response.json()["field"] == "prompt"


def test_one_and_two_character_prompts_rejected(client: TestClient, tmp_path: Path, monkeypatch):
    _enable_llm(monkeypatch)
    project_id = _project(client, tmp_path)
    for value in ("a", "ab", "  a  "):
        response = client.post(
            "/api/agent/tasks",
            json={"project_id": project_id, "prompt": value, "mode": "implement"},
        )
        assert response.status_code == 422, value
        assert response.json()["field"] == "prompt"


def test_three_character_prompt_accepted(client: TestClient, tmp_path: Path, monkeypatch):
    _enable_llm(monkeypatch)
    project_id = _project(client, tmp_path)
    response = client.post("/api/agent/tasks", json={"project_id": project_id, "prompt": "abc", "mode": "implement"})
    assert response.status_code == 200
    assert response.json()["prompt"] == "abc"


def test_normal_task_accepted_and_trimmed(client: TestClient, tmp_path: Path, monkeypatch):
    _enable_llm(monkeypatch)
    project_id = _project(client, tmp_path)
    response = client.post(
        "/api/agent/tasks",
        json={"project_id": project_id, "prompt": "  Fix the bug  ", "mode": "implement"},
    )
    assert response.status_code == 200
    assert response.json()["prompt"] == "Fix the bug"


def test_optional_problem_description_omitted(client: TestClient, tmp_path: Path, monkeypatch):
    _enable_llm(monkeypatch)
    project_id = _project(client, tmp_path)
    response = client.post(
        "/api/agent/tasks",
        json={"project_id": project_id, "prompt": "Fix the discount calculation", "mode": "implement"},
    )
    assert response.status_code == 200
    assert response.json().get("problem_description") in {None, ""}


def test_optional_problem_description_provided(client: TestClient, tmp_path: Path, monkeypatch):
    _enable_llm(monkeypatch)
    project_id = _project(client, tmp_path)
    response = client.post(
        "/api/agent/tasks",
        json={
            "project_id": project_id,
            "prompt": "Fix the discount calculation",
            "mode": "implement",
            "problem_description": "When I apply a 10% discount to ₹53,000, the result is incorrect.",
        },
    )
    assert response.status_code == 200
    assert "₹53,000" in response.json()["problem_description"]
