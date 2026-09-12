"""Project registration, scanning, import, and file browsing."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.database.repository import ProjectRepository, TaskRepository
from app.repository.importer import import_files_to_workspace
from app.repository.scanner import RepositoryScanner
from app.schemas.files import DiffOut
from app.schemas.project import ProjectCreate, ProjectImport, ProjectOut, RepoMapOut
from app.tools.git import GitTool
from app.utils.logging import get_logger
from app.utils.security import SecurityError, normalize_repo_root

router = APIRouter(prefix="/api/projects", tags=["projects"])
scanner = RepositoryScanner()
logger = get_logger(__name__)


def _http_for_repo_error(exc: Exception) -> HTTPException:
    if isinstance(exc, SecurityError):
        message = str(exc)
        lowered = message.lower()
        if "does not exist" in lowered:
            return HTTPException(status_code=404, detail="Repository path does not exist.")
        if "not a directory" in lowered:
            return HTTPException(status_code=400, detail="Repository path is not a directory.")
        if "could not be accessed" in lowered or "permission" in lowered:
            return HTTPException(status_code=403, detail="Repository folder could not be accessed.")
        if "no supported" in lowered or "no files were provided" in lowered or "every file was excluded" in lowered:
            return HTTPException(status_code=400, detail="Repository contains no supported project files.")
        return HTTPException(status_code=400, detail=message)
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail="Repository folder could not be accessed.")
    if isinstance(exc, OSError):
        return HTTPException(status_code=400, detail="Repository scan failed.")
    return HTTPException(status_code=400, detail="Repository scan failed.")


def _repo_map_out(repo_map, git_status: str = "") -> RepoMapOut:
    return RepoMapOut(
        root=repo_map.root,
        project_type=repo_map.project_type,
        file_count=len(repo_map.files),
        files=[{"path": f.path, "kind": f.kind, "size": f.size} for f in repo_map.files],
        config_files=repo_map.config_files,
        test_files=repo_map.test_files,
        dependency_files=repo_map.dependency_files,
        tree=repo_map.tree,
        git_status=git_status,
        scan_status="ok" if repo_map.files else "empty",
    )


def _register_path(db: Session, root_path: str, name: str | None = None) -> ProjectOut:
    root = normalize_repo_root(root_path)
    logger.info("project.register path=%s", root)
    repo_map = scanner.scan(root)
    project = ProjectRepository(db).create(
        name=name or root.name,
        root_path=str(root),
        project_type=repo_map.project_type,
    )
    ProjectRepository(db).save_scan(project, repo_map.to_dict(), repo_map.project_type)
    logger.info("project.registered id=%s type=%s files=%s", project.id, repo_map.project_type, len(repo_map.files))
    return ProjectOut.model_validate(project)


@router.post("", response_model=ProjectOut)
def create_project(body: ProjectCreate, db: Session = Depends(get_db)) -> ProjectOut:
    try:
        return _register_path(db, body.root_path, body.name)
    except (SecurityError, PermissionError, OSError) as exc:
        logger.warning("project.register_failed reason=%s", type(exc).__name__)
        raise _http_for_repo_error(exc) from exc


@router.post("/import", response_model=ProjectOut)
def import_project(body: ProjectImport, db: Session = Depends(get_db)) -> ProjectOut:
    try:
        logger.info("project.import name=%s files=%s", body.name, len(body.files))
        root = import_files_to_workspace(
            body.name,
            [(item.path, item.content) for item in body.files],
        )
        return _register_path(db, str(root), body.name)
    except (SecurityError, PermissionError, OSError) as exc:
        logger.warning("project.import_failed reason=%s", type(exc).__name__)
        raise _http_for_repo_error(exc) from exc


@router.post("/browse")
def browse_folder() -> dict:
    """Open a native folder dialog on this machine (local developer tool)."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askdirectory(title="Select CodePilot project folder")
        root.destroy()
    except Exception as exc:  # pragma: no cover - depends on desktop session
        logger.warning("native folder picker unavailable")
        raise HTTPException(
            status_code=501,
            detail="Folder picker is unavailable in this environment. Use the browser picker or enter a path.",
        ) from exc
    if not selected:
        raise HTTPException(status_code=400, detail="Folder selection was cancelled.")
    try:
        path = str(normalize_repo_root(selected))
    except SecurityError as exc:
        raise _http_for_repo_error(exc) from exc
    logger.info("project.browse selected")
    return {"root_path": path}


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)) -> list[ProjectOut]:
    return [ProjectOut.model_validate(item) for item in ProjectRepository(db).list()]


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)) -> ProjectOut:
    project = ProjectRepository(db).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectOut.model_validate(project)


@router.post("/{project_id}/scan", response_model=RepoMapOut)
def scan_project(project_id: int, db: Session = Depends(get_db)) -> RepoMapOut:
    project = ProjectRepository(db).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    logger.info("project.scan id=%s", project_id)
    try:
        repo_map = scanner.scan(project.root_path)
    except (SecurityError, PermissionError, OSError) as exc:
        logger.warning("project.scan_failed id=%s reason=%s", project_id, type(exc).__name__)
        raise _http_for_repo_error(exc) from exc
    ProjectRepository(db).save_scan(project, repo_map.to_dict(), repo_map.project_type)
    git_status = GitTool(project.root_path).status()
    return _repo_map_out(repo_map, git_status)


@router.get("/{project_id}/diff", response_model=DiffOut)
def project_diff(project_id: int, task_id: int | None = None, db: Session = Depends(get_db)) -> DiffOut:
    project = ProjectRepository(db).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    diff = GitTool(project.root_path).diff()
    changed = []
    if task_id:
        task = TaskRepository(db).get(task_id)
        if task and task.state_json:
            state = json.loads(task.state_json)
            changed = state.get("files_modified") or []
    return DiffOut(task_id=task_id, diff=diff, changed_files=changed)
