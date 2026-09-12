"""Lightweight in-memory file index."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.repository.scanner import FileInfo, RepoMap


@dataclass
class IndexedFile:
    path: str
    kind: str
    size: int
    preview: str


class FileIndexer:
    def index(self, root: Path, repo_map: RepoMap, preview_chars: int = 400) -> list[IndexedFile]:
        indexed: list[IndexedFile] = []
        for info in repo_map.files:
            path = root / info.path
            preview = ""
            try:
                preview = path.read_text(encoding="utf-8", errors="ignore")[:preview_chars]
            except OSError:
                preview = ""
            indexed.append(IndexedFile(path=info.path, kind=info.kind, size=info.size, preview=preview))
        return indexed
