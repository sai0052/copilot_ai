"""Search tool wrapper."""

from __future__ import annotations

from pathlib import Path

from app.repository.search import CodeSearch


class SearchTool:
    def __init__(self, root: str | Path) -> None:
        self.search = CodeSearch(root)

    def search_code(self, query: str, regex: bool = False, filename: str | None = None, mode: str = "text") -> list[dict]:
        if mode == "filename" or filename:
            return self.search.search_filename(filename or query)
        if mode == "symbol":
            return self.search.search_symbols(query)
        if mode == "imports":
            return self.search.search_imports(query)
        return self.search.search(query, regex=regex)
