"""Project API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, computed_field


class ProjectCreate(BaseModel):
    root_path: str = Field(min_length=1)
    name: str | None = None


class ProjectOut(BaseModel):
    id: int
    name: str
    root_path: str
    project_type: str
    created_at: datetime | None = None

    model_config = {"from_attributes": True}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def source(self) -> str:
        normalized = (self.root_path or "").replace("\\", "/").lower()
        return "imported" if "/workspaces/" in normalized else "local_path"


class ProjectImportFile(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    content: str = ""


class ProjectImport(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    files: list[ProjectImportFile]


class FileEntry(BaseModel):
    path: str
    kind: str
    size: int


class RepoMapOut(BaseModel):
    root: str
    project_type: str
    file_count: int
    files: list[FileEntry]
    config_files: list[str]
    test_files: list[str]
    dependency_files: list[str]
    tree: str
    git_status: str = ""
    scan_status: str = "ok"
