"""File API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FileReadQuery(BaseModel):
    path: str = Field(min_length=1)


class FileContentOut(BaseModel):
    path: str
    content: str
    size: int


class DiffOut(BaseModel):
    task_id: int | None = None
    diff: str
    changed_files: list[str]
