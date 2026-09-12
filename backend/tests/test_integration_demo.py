"""Integration: agent modifies demo_fastapi using a stub LLM with tool calls."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agent.orchestrator import AgentOrchestrator
from app.database.database import SessionLocal
from app.database.models import AgentTask, Project
from app.llm.models import LLMResponse, LLMUsage
from app.tools.filesystem import FileSystemTools


DEMO = Path(__file__).resolve().parents[2] / "sample_projects" / "demo_fastapi"


class ScriptedLLM:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, messages, tools=None, temperature=None, response_format=None, **kwargs):
        self.calls += 1
        text = json.dumps([m.model_dump() for m in messages])
        if "implementation plan" in text.lower() or "Produce the implementation" in text:
            return LLMResponse(
                content=json.dumps(
                    {
                        "summary": "Add /health",
                        "steps": [
                            {"index": 1, "title": "Add endpoint", "detail": "Add /health to main.py", "status": "pending"}
                        ],
                        "relevant_files": ["app/main.py"],
                        "tests_to_run": ["pytest"],
                        "risks": [],
                    }
                )
            )
        if tools and self.calls < 6 and "Add a /health" in text:
            return LLMResponse(
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": json.dumps({"path": "app/main.py"}),
                        },
                    }
                ]
            )
        if tools and "tool" in text and "read_file" in text and self.calls < 8:
            new_main = (
                "from fastapi import FastAPI\n\n"
                "from app.routes.items import router as items_router\n\n"
                'app = FastAPI(title="Demo Shop")\n'
                "app.include_router(items_router)\n\n"
                '@app.get("/health")\n'
                "def health() -> dict:\n"
                '    return {"status": "ok"}\n'
            )
            return LLMResponse(
                tool_calls=[
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {
                            "name": "write_file",
                            "arguments": json.dumps({"path": "app/main.py", "content": new_main}),
                        },
                    }
                ]
            )
        if "final engineering report" in text.lower() or "Write a structured final" in text:
            return LLMResponse(
                content=json.dumps(
                    {
                        "task": "Add a /health endpoint.",
                        "status": "SUCCESS",
                        "summary": "Added /health",
                        "files_changed": ["app/main.py"],
                        "tests_executed": "pytest -q",
                        "tests_passed": 1,
                        "tests_failed": 0,
                        "commands_executed": ["pytest -q"],
                        "iterations_used": 1,
                        "decisions": ["Add health to FastAPI app"],
                        "warnings": [],
                    }
                )
            )
        return LLMResponse(content="Added /health endpoint.")


@pytest.mark.asyncio
async def test_agent_adds_health_endpoint(tmp_path, monkeypatch):
    # Copy demo into temp so the test does not dirty the sample forever if it fails mid-way.
    import shutil

    work = tmp_path / "demo"
    shutil.copytree(DEMO, work)
    db = SessionLocal()
    try:
        project = Project(name="demo", root_path=str(work), project_type="fastapi")
        db.add(project)
        db.commit()
        db.refresh(project)
        task = AgentTask(
            project_id=project.id,
            prompt="Add a /health endpoint.",
            mode="implement",
            max_iterations=2,
            status="queued",
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        db.refresh(task, attribute_names=["project"])

        orch = AgentOrchestrator(db, llm=ScriptedLLM())
        events = []

        async def emit(event_type, message, payload=None):
            events.append(event_type)

        report = await orch.run_task(task, emit)
        content = FileSystemTools(work).read_file("app/main.py")
        assert "/health" in content
        assert "agent_started" in events
        assert report.task
    finally:
        db.close()
