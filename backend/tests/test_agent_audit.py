from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import pytest

from app.agent.loop import AgentLoop
from app.agent.orchestrator import AgentOrchestrator
from app.agent.plan_validator import validate_plan
from app.agent.state import AgentState
from app.config import Settings
from app.database.database import SessionLocal, init_db
from app.database.models import AgentTask, Project
from app.execution.command_policy import CommandDenied, validate_command
from app.llm.models import LLMResponse
from app.repository.context import ContextBuilder
from app.repository.scanner import RepositoryScanner
from app.schemas.agent import ImplementationPlan, PlanStep
from app.tools.registry import ToolRegistry

SAMPLE = Path(__file__).resolve().parents[2] / "sample_projects" / "codepilot_error_test_repo"


class PlanThenToolsLLM:
    def __init__(self, tool_forever: bool = False, after_tools: str = "done"):
        self.calls = 0
        self.tool_forever = tool_forever
        self.after_tools = after_tools
        self.settings = _settings()

    async def complete(self, messages, tools=None, **kwargs):
        self.calls += 1
        blob = json.dumps([m.model_dump() for m in messages])
        if "Produce the implementation" in blob or "implementation or analysis plan" in blob:
            return LLMResponse(
                content=json.dumps(
                    {
                        "summary": "Fix discount in cart.py",
                        "steps": [
                            {
                                "index": 1,
                                "title": "Inspect cart.py",
                                "detail": "Read apply_discount",
                                "status": "pending",
                            }
                        ],
                        "relevant_files": ["app/cart.py"],
                        "tests_to_run": ["pytest"],
                        "risks": [],
                    }
                )
            )
        if tools and (self.tool_forever or "read_file" not in blob):
            return LLMResponse(
                tool_calls=[
                    {
                        "id": f"call_{self.calls}",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": json.dumps({"path": "app/cart.py"})},
                    }
                ]
            )
        return LLMResponse(content=self.after_tools)


class FixDiscountLLM:
    def __init__(self):
        self.calls = 0
        self.wrote = False
        self.settings = _settings()

    async def complete(self, messages, tools=None, **kwargs):
        self.calls += 1
        blob = json.dumps([m.model_dump() for m in messages])
        if "Produce the implementation" in blob or "implementation or analysis plan" in blob:
            return LLMResponse(
                content=json.dumps(
                    {
                        "summary": "Correct apply_discount to subtract percent from price",
                        "steps": [
                            {"index": 1, "title": "Fix cart.py", "detail": "Use 1 - percent/100", "status": "pending"},
                            {"index": 2, "title": "Update tests", "detail": "Cover 0/10/50/100", "status": "pending"},
                        ],
                        "relevant_files": ["app/cart.py", "tests/test_cart.py"],
                        "tests_to_run": ["pytest"],
                        "risks": [],
                    }
                )
            )
        if tools and not self.wrote:
            self.wrote = True
            return LLMResponse(
                tool_calls=[
                    {
                        "id": "w1",
                        "type": "function",
                        "function": {
                            "name": "write_file",
                            "arguments": json.dumps(
                                {
                                    "path": "app/cart.py",
                                    "content": (
                                        '"""Cart discount helper."""\n\n\n'
                                        "def apply_discount(price: float, percent: float) -> float:\n"
                                        '    """Return the price after a percent discount (0-100)."""\n'
                                        "    if percent < 0 or percent > 100:\n"
                                        '        raise ValueError("percent must be between 0 and 100")\n'
                                        "    return price * (1 - percent / 100)\n"
                                    ),
                                }
                            ),
                        },
                    },
                    {
                        "id": "w2",
                        "type": "function",
                        "function": {
                            "name": "write_file",
                            "arguments": json.dumps(
                                {
                                    "path": "tests/test_cart.py",
                                    "content": (
                                        "from app.cart import apply_discount\n\n"
                                        "def test_zero_percent_keeps_price():\n"
                                        "    assert apply_discount(100, 0) == 100\n\n"
                                        "def test_ten_percent():\n"
                                        "    assert apply_discount(53000, 10) == 47700\n\n"
                                        "def test_fifty_percent():\n"
                                        "    assert apply_discount(100, 50) == 50\n\n"
                                        "def test_hundred_percent():\n"
                                        "    assert apply_discount(80, 100) == 0\n"
                                    ),
                                }
                            ),
                        },
                    },
                ]
            )
        return LLMResponse(content="Discount calculation fixed and tests added.")


def _settings(**kwargs) -> Settings:
    data = dict(
        llm_api_key="test",
        llm_base_url="https://api.groq.com/openai/v1",
        llm_model="openai/gpt-oss-120b",
        agent_max_iterations=5,
        agent_max_tool_rounds=10,
        agent_task_timeout_seconds=300,
        agent_require_git_branch=False,
        embeddings_enabled=False,
        context_max_tokens=8000,
        file_max_bytes=1_048_576,
        command_timeout_seconds=60,
    )
    data.update(kwargs)
    return Settings.model_construct(**data)


async def _run(tmp_path: Path, llm, settings: Settings, max_iterations: int = 2, prompt: str = "Fix discount"):
    work = tmp_path / "repo"
    shutil.copytree(SAMPLE, work)
    init_db()
    db = SessionLocal()
    try:
        project = Project(name="err", root_path=str(work), project_type="generic_python")
        db.add(project)
        db.commit()
        db.refresh(project)
        task = AgentTask(
            project_id=project.id,
            prompt=prompt,
            mode="implement",
            max_iterations=max_iterations,
            status="queued",
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        db.refresh(task, attribute_names=["project"])
        events = []

        async def emit(event_type, message, payload=None):
            events.append((event_type, message))

        orch = AgentOrchestrator(db, settings=settings, llm=llm)
        report = await orch.run_task(task, emit)
        return report, events, work, db.get(AgentTask, task.id)
    finally:
        db.close()


def test_scanner_detects_error_repo_as_python_not_flask():
    repo = RepositoryScanner().scan(SAMPLE)
    assert repo.project_type == "generic_python"
    paths = {item.path.replace("\\", "/") for item in repo.files}
    assert "app/cart.py" in paths
    assert "app/products.py" in paths
    assert not any("flask" in path.lower() for path in paths)


def test_plan_validation_rejects_flask_on_python():
    plan = ImplementationPlan(
        summary="Install Flask and add /health",
        steps=[
            PlanStep(index=1, title="Install Flask", detail="pip install flask"),
            PlanStep(index=2, title="Add health route", detail="Create a Flask app"),
            PlanStep(index=3, title="Fix cart", detail="Correct apply_discount in app/cart.py"),
        ],
    )
    cleaned = validate_plan(plan, "generic_python")
    blob = " ".join(f"{s.title} {s.detail}" for s in cleaned.steps).lower()
    assert "flask" not in blob
    assert cleaned.risks
    assert any("cart" in s.detail.lower() or "discount" in s.detail.lower() or "inspect" in s.title.lower() for s in cleaned.steps)


def test_pip_install_flask_blocked_on_python_repo():
    with pytest.raises(CommandDenied):
        validate_command("pip install flask", repo_root=str(SAMPLE))


def test_context_skips_readme_and_does_not_inject_flask(tmp_path: Path):
    work = tmp_path / "repo"
    shutil.copytree(SAMPLE, work)
    repo = RepositoryScanner().scan(work)
    bundle = ContextBuilder(work, _settings()).select("Fix the discount calculation /health endpoint", repo)
    paths = [item["path"].replace("\\", "/").lower() for item in bundle["files"]]
    assert bundle["repo_type"] == "generic_python"
    assert any("cart.py" in path for path in paths)
    assert not any(path.endswith("readme.md") for path in paths)


@pytest.mark.asyncio
async def test_tool_round_limit_is_not_success(tmp_path: Path):
    report, events, _work, row = await _run(
        tmp_path,
        PlanThenToolsLLM(tool_forever=True),
        _settings(agent_max_tool_rounds=2, agent_max_iterations=1),
        max_iterations=1,
    )
    assert report.status == "LIMIT_REACHED"
    assert "successfully" not in report.summary.lower()
    assert "tool-round limit" in report.summary.lower()
    assert row.status == "limit_reached"
    assert any(item[0] == "agent_limit_reached" for item in events)
    assert any(item[0] == "limit_reached" for item in events)


@pytest.mark.asyncio
async def test_iteration_limit_is_not_success(tmp_path: Path):
    report, _events, _work, row = await _run(
        tmp_path,
        PlanThenToolsLLM(tool_forever=False, after_tools="I did not change anything"),
        _settings(agent_max_tool_rounds=4, agent_max_iterations=1),
        max_iterations=1,
    )
    assert report.status in {"LIMIT_REACHED", "FAILED"}
    assert report.status != "SUCCESS"
    assert row.status != "success"


@pytest.mark.asyncio
async def test_task_timeout_status(tmp_path: Path):
    report, events, _work, row = await _run(
        tmp_path,
        PlanThenToolsLLM(tool_forever=True),
        _settings(agent_max_tool_rounds=10, agent_task_timeout_seconds=0),
        max_iterations=2,
    )
    assert report.status == "TIMEOUT"
    assert "timeout" in report.summary.lower()
    assert row.status == "timeout"
    assert any(item[0] in {"agent_timeout", "timeout_reached"} for item in events)


@pytest.mark.asyncio
async def test_loop_timeout_without_llm(tmp_path: Path):
    (tmp_path / "x.py").write_text("x=1\n", encoding="utf-8")
    state = AgentState(task="x", max_iterations=3, deadline=time.monotonic() - 1, started_at=time.monotonic())

    class Boom:
        async def run(self, *args, **kwargs):
            raise AssertionError("executor should not run after timeout")

    events = []

    async def emit(event_type, message, payload=None):
        events.append(event_type)

    loop = AgentLoop(Boom(), None, ToolRegistry(str(tmp_path)))  # type: ignore[arg-type]
    await loop.run_implement(state, "ctx", emit)
    assert state.status == "timeout"
    assert "timeout_reached" in events


@pytest.mark.asyncio
async def test_successful_mocked_discount_fix(tmp_path: Path):
    report, events, work, row = await _run(
        tmp_path,
        FixDiscountLLM(),
        _settings(agent_max_tool_rounds=8, agent_max_iterations=2),
        max_iterations=2,
        prompt="Fix the discount calculation and add tests.",
    )
    assert report.status == "SUCCESS"
    assert row.status == "success"
    assert "app/cart.py" in report.files_changed
    text = (work / "app" / "cart.py").read_text(encoding="utf-8")
    assert "1 - percent" in text
    assert "flask" not in text.lower()
    assert report.tests_failed == 0
    assert report.tests_passed >= 4
    assert any(item[0] == "agent_completed" for item in events)
    assert report.duration_seconds >= 0
    assert report.tool_rounds >= 1
    assert report.plan
    assert all(step["status"] != "PENDING" for step in report.plan if step.get("kind") != "commit")
    assert not any(step["status"] == "PENDING" and step.get("kind") in {"inspect", "implement", "test"} for step in report.plan)


def test_create_task_accepts_task_alias(client, tmp_path: Path, monkeypatch):
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
        json={"project_id": project_id, "task": "Fix the discount calculation", "mode": "implement"},
    )
    assert response.status_code == 200
    assert response.json()["prompt"] == "Fix the discount calculation"
    assert response.json()["status"] == "queued"
