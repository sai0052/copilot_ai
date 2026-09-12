"""Persistence helpers for projects, tasks, events, and execution records."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    AgentEvent,
    AgentTask,
    CommandExecution,
    FileChange,
    FileSnapshot,
    Project,
    TestRun,
)


class ProjectRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, name: str, root_path: str, project_type: str = "unknown") -> Project:
        existing = self.get_by_path(root_path)
        if existing:
            existing.name = name
            existing.project_type = project_type
            self.db.commit()
            self.db.refresh(existing)
            return existing
        project = Project(name=name, root_path=root_path, project_type=project_type)
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def list(self) -> list[Project]:
        return list(self.db.scalars(select(Project).order_by(Project.id.desc())))

    def get(self, project_id: int) -> Project | None:
        return self.db.get(Project, project_id)

    def get_by_path(self, root_path: str) -> Project | None:
        return self.db.scalar(select(Project).where(Project.root_path == root_path))

    def save_scan(self, project: Project, scan: dict[str, Any], project_type: str) -> Project:
        project.last_scan_json = json.dumps(scan)
        project.project_type = project_type
        self.db.commit()
        self.db.refresh(project)
        return project


class TaskRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        project_id: int,
        prompt: str,
        mode: str,
        max_iterations: int,
        problem_description: str | None = None,
    ) -> AgentTask:
        task = AgentTask(
            project_id=project_id,
            prompt=prompt,
            mode=mode,
            max_iterations=max_iterations,
            status="queued",
            problem_description=problem_description,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def get(self, task_id: int) -> AgentTask | None:
        return self.db.get(AgentTask, task_id)

    def save(self, task: AgentTask) -> AgentTask:
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def add_event(self, task_id: int, event_type: str, message: str, payload: dict[str, Any] | None = None) -> AgentEvent:
        event = AgentEvent(
            task_id=task_id,
            event_type=event_type,
            message=message,
            payload_json=json.dumps(payload) if payload else None,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def events(self, task_id: int) -> list[AgentEvent]:
        return list(
            self.db.scalars(
                select(AgentEvent).where(AgentEvent.task_id == task_id).order_by(AgentEvent.id.asc())
            )
        )

    def add_snapshot(self, task_id: int, path: str, content: str) -> FileSnapshot:
        snap = FileSnapshot(task_id=task_id, path=path, content=content)
        self.db.add(snap)
        self.db.commit()
        return snap

    def add_change(self, task_id: int, path: str, action: str, diff: str | None) -> FileChange:
        change = FileChange(task_id=task_id, path=path, action=action, diff=diff)
        self.db.add(change)
        self.db.commit()
        return change

    def add_command(
        self,
        task_id: int,
        command: str,
        exit_code: int | None,
        stdout: str,
        stderr: str,
        duration_ms: int,
    ) -> CommandExecution:
        row = CommandExecution(
            task_id=task_id,
            command=command,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
        )
        self.db.add(row)
        self.db.commit()
        return row

    def add_test_run(
        self,
        task_id: int,
        command: str,
        passed: int,
        failed: int,
        exit_code: int,
        output: str,
        duration_ms: int,
    ) -> TestRun:
        row = TestRun(
            task_id=task_id,
            command=command,
            passed=passed,
            failed=failed,
            exit_code=exit_code,
            output=output,
            duration_ms=duration_ms,
        )
        self.db.add(row)
        self.db.commit()
        return row

    def mark_complete(self, task: AgentTask, status: str, report: dict[str, Any] | None = None) -> AgentTask:
        task.status = status
        task.completed_at = datetime.utcnow()
        if report is not None:
            task.report_json = json.dumps(report)
        return self.save(task)
