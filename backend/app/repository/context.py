"""Token-aware context selection for LLM prompts."""

from __future__ import annotations

import re
from pathlib import Path

from app.config import Settings, get_settings
from app.repository.scanner import RepoMap
from app.repository.search import CodeSearch
from app.utils.security import is_secret_file

TASK_KEYWORDS = {
    "auth": ["auth", "jwt", "login", "token", "oauth", "password", "session"],
    "health": ["health", "ready", "live"],
    "db": ["database", "sqlalchemy", "model", "migration"],
    "api": ["router", "route", "endpoint"],
    "fastapi": ["fastapi"],
    "flask": ["flask"],
    "test": ["pytest", "test", "assert"],
    "discount": ["discount", "cart", "price", "percent", "checkout"],
}

SKIP_UNLESS_ASKED = {"readme.md", "license", "license.md", "changelog.md"}


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class ContextBuilder:
    def __init__(self, root: Path, settings: Settings | None = None) -> None:
        self.root = Path(root).resolve()
        self.settings = settings or get_settings()
        self.search = CodeSearch(self.root)

    def select(
        self,
        task: str,
        repo_map: RepoMap,
        extra_paths: list[str] | None = None,
    ) -> dict:
        ranked = self._rank_files(task, repo_map, extra_paths or [])
        budget = max(512, int(self.settings.context_max_tokens * 0.45))
        selected: list[dict] = []
        summaries: list[dict] = []
        used = 0
        mention_docs = "readme" in task.lower()
        for path, score in ranked:
            name = Path(path).name.lower()
            if name in SKIP_UNLESS_ASKED and not mention_docs:
                summaries.append({"path": path, "summary": "documentation omitted from context", "score": score})
                continue
            file_path = self.root / path
            if not file_path.is_file() or is_secret_file(file_path):
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if len(content.encode("utf-8")) > self.settings.file_max_bytes:
                summaries.append({"path": path, "summary": content[:240], "score": score})
                continue
            snippet = _clip(content, 1200)
            tokens = estimate_tokens(snippet)
            if len(selected) < 6 and (used + tokens <= budget or score > 20):
                selected.append({"path": path, "content": snippet, "score": score})
                used += tokens
            else:
                summaries.append({"path": path, "summary": content[:180], "score": score})
            if used >= budget or len(selected) >= 6:
                break
        tree = "\n".join((repo_map.tree or "").splitlines()[:40])
        return {
            "files": selected,
            "summaries": summaries[:12],
            "repo_type": repo_map.project_type,
            "tree": tree[:1500],
            "config_files": repo_map.config_files[:20],
            "test_files": repo_map.test_files[:20],
        }

    def _rank_files(self, task: str, repo_map: RepoMap, extra_paths: list[str]) -> list[tuple[str, int]]:
        scores: dict[str, int] = {}
        lowered = task.lower()
        keywords = set(re_split(lowered))
        for group, words in TASK_KEYWORDS.items():
            if any(word in lowered for word in words):
                keywords.update(words)
                keywords.add(group)
        search_hits = []
        for keyword in list(keywords)[:8]:
            search_hits.extend(self.search.search(keyword, max_results=12))
        for hit in search_hits:
            scores[hit["path"]] = scores.get(hit["path"], 0) + 8
        for path in extra_paths:
            scores[path] = scores.get(path, 0) + 15
        for info in repo_map.files:
            score = scores.get(info.path, 0)
            name = info.path.lower()
            if any(word in name for word in keywords):
                score += 10
            if info.path in repo_map.config_files:
                score += 4
            if info.path in repo_map.dependency_files:
                score += 5
            if info.path in repo_map.test_files:
                score += 3
            if name.endswith("main.py") or name.endswith("app.py") or name.endswith("cart.py"):
                score += 6
            if score:
                scores[info.path] = score
        return sorted(scores.items(), key=lambda item: item[1], reverse=True)


def re_split(text: str) -> list[str]:
    return [part for part in re.findall(r"[a-zA-Z0-9_]+", text.lower()) if len(part) > 2]


def _clip(content: str, max_chars: int) -> str:
    if len(content) <= max_chars:
        return content
    return content[:max_chars] + "\n... [truncated; use read_file for the rest] ..."


def render_context(bundle: dict) -> str:
    parts = [
        f"Project type: {bundle.get('repo_type')}",
        "Repository tree (truncated):",
        bundle.get("tree", "")[:1500],
        "High-priority files (read others with tools if needed):",
    ]
    for item in bundle.get("files", []):
        parts.append(f"\nFILE: {item['path']}\n```\n{item['content']}\n```")
    if bundle.get("summaries"):
        parts.append("\nOther files (summaries only):")
        for item in bundle["summaries"][:8]:
            parts.append(f"- {item['path']}: {item['summary'][:120]}")
    return "\n".join(parts)


def render_plan_context(bundle: dict) -> str:
    files = bundle.get("files") or []
    names = [item["path"] for item in files]
    snippets = []
    for item in files[:5]:
        snippets.append(f"{item['path']}:\n{item['content'][:600]}")
    return (
        f"Project type: {bundle.get('repo_type')}\n"
        f"Relevant files: {', '.join(names)}\n"
        f"Tree:\n{bundle.get('tree', '')[:800]}\n\n"
        + "\n\n".join(snippets)
    )
