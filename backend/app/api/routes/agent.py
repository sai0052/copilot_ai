"""Agent task lifecycle and SSE stream."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.agent.hints import normalize_problem_description
from app.agent.orchestrator import AgentOrchestrator
from app.api.dependencies import get_db
from app.api.events import dump, history, is_cancelled, publish, request_cancel, subscribe, unsubscribe
from app.config import get_settings
from app.database.database import SessionLocal
from app.database.repository import ProjectRepository, TaskRepository
from app.schemas.agent import AgentEventOut, FinalReport, TaskCreate, TaskOut

router = APIRouter(prefix="/api/agent", tags=["agent"])


def _to_out(task) -> TaskOut:
    report = None
    plan: list = []
    if task.report_json:
        try:
            report = FinalReport.model_validate(json.loads(task.report_json))
            plan = list(report.plan or [])
        except Exception:
            report = None
    if not plan and task.state_json:
        try:
            plan = list(json.loads(task.state_json).get("plan") or [])
        except Exception:
            plan = []
    return TaskOut(
        id=task.id,
        project_id=task.project_id,
        prompt=task.prompt,
        mode=task.mode,
        status=task.status,
        phase=task.phase,
        iteration=task.iteration,
        max_iterations=task.max_iterations,
        branch_name=task.branch_name,
        error=task.error,
        report=report,
        problem_description=getattr(task, "problem_description", None),
        plan=plan,
        created_at=task.created_at,
    )


@router.post("/tasks", response_model=TaskOut)
async def create_task(body: TaskCreate, db: Session = Depends(get_db)) -> TaskOut:
    project = ProjectRepository(db).get(body.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    settings = get_settings()
    if not settings.llm_is_configured:
        raise HTTPException(
            status_code=400,
            detail="LLM unavailable. Configure the server API key in .env and restart the backend.",
        )
    max_iterations = body.max_iterations or settings.agent_max_iterations
    description = normalize_problem_description(body.problem_description)
    task = TaskRepository(db).create(
        project.id,
        body.prompt,
        body.mode.value,
        max_iterations,
        problem_description=description,
    )
    asyncio.create_task(_run(task.id))
    return _to_out(task)


@router.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(task_id: int, db: Session = Depends(get_db)) -> TaskOut:
    task = TaskRepository(db).get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return _to_out(task)


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: int, db: Session = Depends(get_db)) -> dict:
    task = TaskRepository(db).get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    request_cancel(task_id)
    task.status = "cancelled"
    task.phase = "failed"
    TaskRepository(db).save(task)
    return {"ok": True, "status": "cancelled"}


@router.post("/tasks/{task_id}/rollback")
def rollback_task(task_id: int, db: Session = Depends(get_db)) -> dict:
    from app.tools.git import GitTool

    task = TaskRepository(db).get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    message = GitTool(task.project.root_path).rollback()
    return {"ok": True, "message": message}


@router.get("/tasks/{task_id}/events")
async def stream_events(task_id: int) -> StreamingResponse:
    queue = subscribe(task_id)

    async def generate():
        try:
            for event in history(task_id):
                yield f"data: {dump(event)}\n\n"
            while True:
                event = await queue.get()
                yield f"data: {dump(event)}\n\n"
                if event["event"] in {
                    "agent_completed",
                    "agent_failed",
                    "agent_cancelled",
                    "agent_limit_reached",
                    "agent_timeout",
                }:
                    break
        finally:
            unsubscribe(task_id, queue)

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/tasks/{task_id}/history", response_model=list[AgentEventOut])
def event_history(task_id: int, db: Session = Depends(get_db)) -> list[AgentEventOut]:
    repo = TaskRepository(db)
    if not repo.get(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    rows = repo.events(task_id)
    out = []
    for row in rows:
        payload = json.loads(row.payload_json) if row.payload_json else None
        out.append(
            AgentEventOut(
                id=row.id,
                event_type=row.event_type,
                message=row.message,
                payload=payload,
                created_at=row.created_at,
            )
        )
    return out


async def _run(task_id: int) -> None:
    db = SessionLocal()
    try:
        repo = TaskRepository(db)
        task = repo.get(task_id)
        if not task:
            return

        async def emit(event_type: str, message: str, payload: dict | None = None) -> None:
            if is_cancelled(task_id):
                task.status = "cancelled"
            repo.add_event(task_id, event_type, message, payload)
            await publish(task_id, event_type, message, payload)

        orchestrator = AgentOrchestrator(db)
        await orchestrator.run_task(task, emit)
    finally:
        db.close()
