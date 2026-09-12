"""File browse helpers used by project routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.database.repository import ProjectRepository
from app.schemas.files import FileContentOut
from app.tools.filesystem import FileSystemTools
from app.utils.security import SecurityError

router = APIRouter(prefix="/api/projects", tags=["files"])


@router.get("/{project_id}/files")
def list_project_files(project_id: int, directory: str = ".", db: Session = Depends(get_db)) -> dict:
    project = ProjectRepository(db).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        files = FileSystemTools(project.root_path).list_files(directory)
    except SecurityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"files": files}


@router.get("/{project_id}/file", response_model=FileContentOut)
def read_project_file(project_id: int, path: str = Query(...), db: Session = Depends(get_db)) -> FileContentOut:
    project = ProjectRepository(db).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        content = FileSystemTools(project.root_path).read_file(path)
    except SecurityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FileContentOut(path=path, content=content, size=len(content.encode("utf-8")))
