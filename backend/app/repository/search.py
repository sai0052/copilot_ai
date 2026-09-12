"""Repository search: ripgrep when available, Python fallback otherwise."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from app.repository.parser import parse_file
from app.repository.scanner import IGNORE_DIRS
from app.utils.security import is_binary_file, is_secret_file, resolve_inside_repo


class CodeSearch:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def search(
        self,
        query: str,
        regex: bool = False,
        filename: str | None = None,
        max_results: int = 50,
    ) -> list[dict]:
        if filename:
            return self.search_filename(filename, max_results)
        if shutil.which("rg"):
            try:
                hits = self._ripgrep(query, regex=regex, max_results=max_results)
                if hits:
                    return hits
            except (OSError, subprocess.SubprocessError, ValueError):
                pass
        return self._python_search(query, regex=regex, max_results=max_results)

    def search_filename(self, name: str, max_results: int = 50) -> list[dict]:
        needle = name.lower()
        hits: list[dict] = []
        for path in self.root.rglob("*"):
            if any(part in IGNORE_DIRS for part in path.relative_to(self.root).parts):
                continue
            if path.is_file() and needle in path.name.lower():
                hits.append({"path": path.relative_to(self.root).as_posix(), "line": 0, "text": path.name})
                if len(hits) >= max_results:
                    break
        return hits

    def search_symbols(self, name: str, max_results: int = 50) -> list[dict]:
        hits: list[dict] = []
        for path in self.root.rglob("*.py"):
            if any(part in IGNORE_DIRS for part in path.relative_to(self.root).parts) or is_secret_file(path):
                continue
            try:
                parsed = parse_file(path)
            except OSError:
                continue
            for kind in ("classes", "functions"):
                if name in parsed.get(kind, []):
                    hits.append(
                        {
                            "path": path.relative_to(self.root).as_posix(),
                            "line": 0,
                            "text": f"{kind[:-1]} {name}",
                        }
                    )
                    if len(hits) >= max_results:
                        return hits
        return hits

    def search_imports(self, module: str, max_results: int = 50) -> list[dict]:
        return self.search(rf"^\s*(from\s+{re.escape(module)}|import\s+{re.escape(module)})", regex=True, max_results=max_results)

    def _ripgrep(self, query: str, regex: bool, max_results: int) -> list[dict]:
        args = ["rg", "-n", "--hidden", "--no-heading", "--color", "never", "-m", str(max_results)]
        for ignored in IGNORE_DIRS:
            args.extend(["-g", f"!{ignored}"])
        if not regex:
            args.append("-F")
        args.extend([query, str(self.root)])
        completed = subprocess.run(args, capture_output=True, text=True, check=False, timeout=20)
        hits: list[dict] = []
        pattern = re.compile(r"^(.*?):(\d+):(.*)$")
        for line in completed.stdout.splitlines()[:max_results]:
            match = pattern.match(line)
            if not match:
                continue
            raw_path, line_no, text = match.group(1), match.group(2), match.group(3)
            try:
                resolved = Path(raw_path).resolve()
                rel = resolved.relative_to(self.root).as_posix()
            except ValueError:
                continue
            hits.append({"path": rel, "line": int(line_no), "text": text.strip()[:300]})
        return hits

    def _python_search(self, query: str, regex: bool, max_results: int) -> list[dict]:
        pattern = re.compile(query if regex else re.escape(query))
        hits: list[dict] = []
        for path in self.root.rglob("*"):
            if any(part in IGNORE_DIRS for part in path.relative_to(self.root).parts):
                continue
            if not path.is_file() or is_secret_file(path) or is_binary_file(path):
                continue
            if path.stat().st_size > 1_000_000:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for idx, line in enumerate(text.splitlines(), start=1):
                if pattern.search(line):
                    hits.append(
                        {
                            "path": path.relative_to(self.root).as_posix(),
                            "line": idx,
                            "text": line.strip()[:300],
                        }
                    )
                    if len(hits) >= max_results:
                        return hits
        return hits


def safe_search_path(root: Path, relative: str) -> Path:
    return resolve_inside_repo(root, relative)
