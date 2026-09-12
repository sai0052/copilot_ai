"""Git helpers with conservative defaults."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.execution.sandbox import Sandbox


class GitTool:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.sandbox = Sandbox(root)

    def is_repo(self) -> bool:
        return (self.root / ".git").exists()

    def status(self) -> str:
        if not self.is_repo():
            return "Not a git repository"
        return self.sandbox.run("git status --short").stdout

    def diff(self) -> str:
        if not self.is_repo():
            return ""
        result = self.sandbox.run("git diff")
        cached = self.sandbox.run("git diff --cached")
        return (result.stdout + "\n" + cached.stdout).strip()

    def create_task_branch(self) -> str | None:
        if not self.is_repo():
            return None
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        name = f"codepilot/task/{stamp}"
        current = self.sandbox.run("git rev-parse --abbrev-ref HEAD")
        if current.exit_code != 0:
            return None
        created = self.sandbox.run(f"git checkout -b {name}")
        if created.exit_code != 0:
            return None
        return name

    def rollback(self) -> str:
        if self.is_repo():
            restored = self.sandbox.run("git restore .")
            return restored.stdout or restored.stderr or "Restored working tree"
        folder = self.root / ".codepilot_snapshots"
        if not folder.exists():
            return "Not a git repository"
        from app.utils.security import resolve_inside_repo

        restored: list[str] = []
        for snap in folder.iterdir():
            if not snap.is_file():
                continue
            relative = snap.name.replace("__", "/")
            target = resolve_inside_repo(self.root, relative)
            previous = snap.read_text(encoding="utf-8")
            if previous:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(previous, encoding="utf-8")
            elif target.exists() and target.is_file():
                target.unlink()
            restored.append(relative)
        return f"Restored {len(restored)} files from local snapshots"
