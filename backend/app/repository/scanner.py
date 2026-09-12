"""Repository scanner and project-type detection."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.utils.security import is_binary_file, is_secret_file, normalize_repo_root

IGNORE_DIRS = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    "dist",
    "build",
    ".next",
    ".turbo",
    ".cache",
    ".pytest_cache",
    ".mypy_cache",
    "coverage",
    "htmlcov",
    ".idea",
    ".vscode",
    "data",
    ".codepilot_snapshots",
    ".embeddings",
}

CODE_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".json": "json",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".md": "markdown",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "config",
    ".txt": "text",
    ".css": "css",
    ".html": "html",
    ".sql": "sql",
}

CONFIG_NAMES = {
    "pyproject.toml",
    "setup.cfg",
    "setup.py",
    "requirements.txt",
    "package.json",
    "tsconfig.json",
    "vite.config.ts",
    "vite.config.js",
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    ".gitignore",
    "pytest.ini",
    "alembic.ini",
}

DEPENDENCY_NAMES = {
    "requirements.txt",
    "pyproject.toml",
    "package.json",
    "poetry.lock",
    "package-lock.json",
    "pnpm-lock.yaml",
    "Pipfile",
}


@dataclass
class FileInfo:
    path: str
    kind: str
    size: int


@dataclass
class RepoMap:
    root: str
    project_type: str
    files: list[FileInfo] = field(default_factory=list)
    config_files: list[str] = field(default_factory=list)
    test_files: list[str] = field(default_factory=list)
    dependency_files: list[str] = field(default_factory=list)
    tree: str = ""

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "project_type": self.project_type,
            "file_count": len(self.files),
            "files": [info.__dict__ for info in self.files],
            "config_files": self.config_files,
            "test_files": self.test_files,
            "dependency_files": self.dependency_files,
            "tree": self.tree,
        }


class RepositoryScanner:
    def scan(self, root: str | Path, max_files: int = 4000) -> RepoMap:
        repo = normalize_repo_root(root)
        files: list[FileInfo] = []
        config_files: list[str] = []
        test_files: list[str] = []
        dependency_files: list[str] = []

        try:
            iterator = repo.rglob("*")
        except OSError as exc:
            raise PermissionError(f"Cannot scan repository: {exc}") from exc

        for path in iterator:
            if len(files) >= max_files:
                break
            try:
                rel_path = path.relative_to(repo)
            except ValueError:
                continue
            if any(part in IGNORE_DIRS for part in rel_path.parts):
                continue
            try:
                if not path.is_file():
                    continue
                if is_secret_file(path) or is_binary_file(path):
                    continue
                size = path.stat().st_size
            except (PermissionError, OSError):
                continue
            rel = path.relative_to(repo).as_posix()
            kind = CODE_EXTENSIONS.get(path.suffix.lower(), "other")
            if path.name.lower() in {"dockerfile", "makefile"}:
                kind = "config"
            if size > 2_000_000:
                continue
            files.append(FileInfo(path=rel, kind=kind, size=size))
            if path.name.lower() in CONFIG_NAMES or path.name.lower() == "dockerfile":
                config_files.append(rel)
            if path.name.lower() in {n.lower() for n in DEPENDENCY_NAMES}:
                dependency_files.append(rel)
            if self._is_test_file(rel):
                test_files.append(rel)

        project_type = self.detect_project_type(repo, files)
        tree = self._build_tree(files)
        return RepoMap(
            root=str(repo),
            project_type=project_type,
            files=files,
            config_files=sorted(set(config_files)),
            test_files=sorted(set(test_files)),
            dependency_files=sorted(set(dependency_files)),
            tree=tree,
        )

    def detect_project_type(self, root: Path, files: list[FileInfo]) -> str:
        names = {Path(item.path).name.lower() for item in files}
        paths = {item.path.lower() for item in files}
        contents_hints = self._read_hints(root, files)

        if "package.json" in names:
            package = contents_hints.get("package.json", "")
            has_vite = any(name.startswith("vite.config.") for name in names) or "vite" in package
            if "next" in package or any(name.startswith("next.config.") for name in names):
                return "nextjs"
            if "react" in package and has_vite:
                return "react_vite"
            if "react" in package:
                return "react"
            if has_vite:
                return "vite"
            return "nodejs"
        if any("manage.py" in path for path in paths) or "django" in contents_hints.get("requirements.txt", ""):
            return "django"
        if "fastapi" in contents_hints.get("requirements.txt", "") or "fastapi" in contents_hints.get("pyproject.toml", ""):
            return "fastapi"
        if "flask" in contents_hints.get("requirements.txt", "") or "flask" in contents_hints.get("pyproject.toml", ""):
            return "flask"
        if any(item.kind == "python" for item in files):
            if any("console_scripts" in contents_hints.get(name, "") for name in contents_hints):
                return "python_cli"
            return "generic_python"
        return "unknown"

    def _read_hints(self, root: Path, files: list[FileInfo]) -> dict[str, str]:
        hints: dict[str, str] = {}
        interesting = {"requirements.txt", "pyproject.toml", "package.json"}
        for item in files:
            name = Path(item.path).name.lower()
            if name in interesting:
                try:
                    hints[name] = (root / item.path).read_text(encoding="utf-8", errors="ignore").lower()
                except OSError:
                    continue
        return hints

    def _is_test_file(self, rel: str) -> bool:
        lower = rel.lower()
        name = Path(lower).name
        return (
            "/tests/" in f"/{lower}"
            or name.startswith("test_")
            or name.endswith("_test.py")
            or name.endswith(".test.ts")
            or name.endswith(".test.js")
            or name.endswith(".spec.ts")
            or name.endswith(".spec.tsx")
        )

    def _build_tree(self, files: list[FileInfo], limit: int = 400) -> str:
        paths = sorted(item.path.replace("\\", "/") for item in files[:limit])
        lines: list[str] = []
        seen: set[str] = set()
        for path in paths:
            parts = [part for part in path.split("/") if part]
            acc = ""
            for depth, part in enumerate(parts):
                acc = f"{acc}/{part}" if acc else part
                if acc in seen:
                    continue
                seen.add(acc)
                lines.append(f"{'  ' * depth}{part}")
        if len(files) > limit:
            lines.append(f"... {len(files) - limit} more files")
        return "\n".join(lines)
