from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.agent.hints import normalize_problem_description, problem_hint_block
from app.agent.planner import PlanningEngine
from app.llm.models import LLMResponse


def test_normalize_empty_and_whitespace():
    assert normalize_problem_description(None) is None
    assert normalize_problem_description("") is None
    assert normalize_problem_description("   ") is None
    assert normalize_problem_description("undefined") is None
    assert normalize_problem_description("null") is None
    assert problem_hint_block("  ") == ""
    assert "UNTRUSTED HINT" not in problem_hint_block(None)


def test_normalize_keeps_real_text_and_redacts_secrets():
    text = normalize_problem_description("The API returns 500\nLLM_API_KEY=secretvalue")
    assert text is not None
    assert "500" in text
    assert "secretvalue" not in text
    block = problem_hint_block("Discount on ₹53,000 is wrong.")
    assert "₹53,000" in block
    assert "UNTRUSTED HINT" in block


def test_create_task_without_problem_description(client: TestClient, tmp_path: Path, monkeypatch):
    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")
    project_id = client.post("/api/projects", json={"root_path": str(tmp_path)}).json()["id"]

    class FakeSettings:
        agent_max_iterations = 2
        llm_is_configured = True

    async def fake_run(task_id: int) -> None:
        return None

    monkeypatch.setattr("app.api.routes.agent.get_settings", lambda: FakeSettings())
    monkeypatch.setattr("app.api.routes.agent._run", fake_run)
    response = client.post(
        "/api/agent/tasks",
        json={"project_id": project_id, "prompt": "Fix the discount calculation.", "mode": "implement"},
    )
    assert response.status_code == 200
    assert response.json().get("problem_description") in {None, ""}


def test_create_task_with_problem_description(client: TestClient, tmp_path: Path, monkeypatch):
    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")
    project_id = client.post("/api/projects", json={"root_path": str(tmp_path)}).json()["id"]

    class FakeSettings:
        agent_max_iterations = 2
        llm_is_configured = True

    async def fake_run(task_id: int) -> None:
        return None

    monkeypatch.setattr("app.api.routes.agent.get_settings", lambda: FakeSettings())
    monkeypatch.setattr("app.api.routes.agent._run", fake_run)
    description = "When I apply 10% discount to ₹53,000, the result is incorrect.\nExpected 47700."
    response = client.post(
        "/api/agent/tasks",
        json={
            "project_id": project_id,
            "prompt": "Fix the discount calculation.",
            "mode": "implement",
            "problem_description": description,
        },
    )
    assert response.status_code == 200
    assert "₹53,000" in response.json()["problem_description"]
    fetched = client.get(f"/api/agent/tasks/{response.json()['id']}")
    assert fetched.json()["problem_description"] == response.json()["problem_description"]


def test_multiline_special_chars_and_error_message(client: TestClient, tmp_path: Path, monkeypatch):
    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")
    project_id = client.post("/api/projects", json={"root_path": str(tmp_path)}).json()["id"]

    class FakeSettings:
        agent_max_iterations = 2
        llm_is_configured = True

    async def fake_run(task_id: int) -> None:
        return None

    monkeypatch.setattr("app.api.routes.agent.get_settings", lambda: FakeSettings())
    monkeypatch.setattr("app.api.routes.agent._run", fake_run)
    description = "Error: KeyError: 'user'\nSteps: GET /users/999\nActual: 500 & <html>"
    response = client.post(
        "/api/agent/tasks",
        json={
            "project_id": project_id,
            "prompt": "Fix the users endpoint.",
            "mode": "implement",
            "problem_description": description,
        },
    )
    assert response.status_code == 200
    stored = response.json()["problem_description"]
    assert "KeyError" in stored
    assert "/users/999" in stored
    assert "<html>" in stored


def test_whitespace_only_description_is_absent(client: TestClient, tmp_path: Path, monkeypatch):
    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")
    project_id = client.post("/api/projects", json={"root_path": str(tmp_path)}).json()["id"]

    class FakeSettings:
        agent_max_iterations = 2
        llm_is_configured = True

    async def fake_run(task_id: int) -> None:
        return None

    monkeypatch.setattr("app.api.routes.agent.get_settings", lambda: FakeSettings())
    monkeypatch.setattr("app.api.routes.agent._run", fake_run)
    response = client.post(
        "/api/agent/tasks",
        json={
            "project_id": project_id,
            "prompt": "Fix the discount calculation.",
            "mode": "implement",
            "problem_description": "   \n\t  ",
        },
    )
    assert response.status_code == 200
    assert response.json()["problem_description"] in {None, ""}


class CaptureLLM:
    def __init__(self) -> None:
        self.user = ""

    async def complete(self, messages, **kwargs):
        self.user = messages[-1].content or ""
        return LLMResponse(
            content='{"summary":"Inspect cart.py","steps":[{"index":1,"title":"Read cart","detail":"Inspect apply_discount","status":"pending"}],"relevant_files":["app/cart.py"],"tests_to_run":["pytest"],"risks":[]}'
        )


async def test_hint_is_passed_to_planner():
    llm = CaptureLLM()
    await PlanningEngine(llm).create_plan(
        "Fix the discount calculation.",
        "app/cart.py",
        "implement",
        problem_description="10% of 53000 is wrong",
    )
    assert "Fix the discount calculation." in llm.user
    assert "10% of 53000 is wrong" in llm.user
    assert "UNTRUSTED HINT" in llm.user


async def test_hint_omitted_from_planner_when_empty():
    llm = CaptureLLM()
    await PlanningEngine(llm).create_plan("Fix the discount calculation.", "app/cart.py", "implement", problem_description="   ")
    assert "UNTRUSTED HINT" not in llm.user
    assert "undefined" not in llm.user
    assert "null" not in llm.user
