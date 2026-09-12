"""SQLAlchemy persistence models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    root_path: Mapped[str] = mapped_column(String(2000), unique=True)
    project_type: Mapped[str] = mapped_column(String(64), default="unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    last_scan_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    tasks: Mapped[list[AgentTask]] = relationship(back_populates="project")


class AgentTask(Base):
    __tablename__ = "agent_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    prompt: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String(32), default="implement")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    phase: Mapped[str] = mapped_column(String(32), default="queued")
    iteration: Mapped[int] = mapped_column(Integer, default=0)
    max_iterations: Mapped[int] = mapped_column(Integer, default=5)
    branch_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    problem_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    state_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    project: Mapped[Project] = relationship(back_populates="tasks")
    events: Mapped[list[AgentEvent]] = relationship(back_populates="task")
    snapshots: Mapped[list[FileSnapshot]] = relationship(back_populates="task")
    changes: Mapped[list[FileChange]] = relationship(back_populates="task")
    commands: Mapped[list[CommandExecution]] = relationship(back_populates="task")
    tests: Mapped[list[TestRun]] = relationship(back_populates="task")


class AgentEvent(Base):
    __tablename__ = "agent_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("agent_tasks.id"))
    event_type: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    task: Mapped[AgentTask] = relationship(back_populates="events")


class FileSnapshot(Base):
    __tablename__ = "file_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("agent_tasks.id"))
    path: Mapped[str] = mapped_column(String(2000))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    task: Mapped[AgentTask] = relationship(back_populates="snapshots")


class FileChange(Base):
    __tablename__ = "file_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("agent_tasks.id"))
    path: Mapped[str] = mapped_column(String(2000))
    action: Mapped[str] = mapped_column(String(32))
    diff: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    task: Mapped[AgentTask] = relationship(back_populates="changes")


class CommandExecution(Base):
    __tablename__ = "command_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("agent_tasks.id"))
    command: Mapped[str] = mapped_column(Text)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stdout: Mapped[str] = mapped_column(Text, default="")
    stderr: Mapped[str] = mapped_column(Text, default="")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    task: Mapped[AgentTask] = relationship(back_populates="commands")


class TestRun(Base):
    __tablename__ = "test_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("agent_tasks.id"))
    command: Mapped[str] = mapped_column(Text)
    passed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    exit_code: Mapped[int] = mapped_column(Integer, default=1)
    output: Mapped[str] = mapped_column(Text, default="")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    task: Mapped[AgentTask] = relationship(back_populates="tests")
