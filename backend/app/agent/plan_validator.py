"""Reject LLM plans that fight the existing repository architecture."""

from __future__ import annotations

import re

from app.schemas.agent import ImplementationPlan, PlanStep

_FRAMEWORKS = {
    "flask": {"flask"},
    "django": {"django"},
    "fastapi": {"fastapi", "starlette", "uvicorn"},
    "react": {"react", "next.js", "nextjs"},
}

_COMPATIBLE = {
    "generic_python": set(),
    "python_cli": set(),
    "fastapi": {"fastapi", "starlette", "uvicorn"},
    "flask": {"flask"},
    "django": {"django"},
    "nodejs": set(),
    "react": {"react"},
    "react_vite": {"react", "vite"},
    "vite": {"vite"},
    "nextjs": {"react", "next", "next.js", "nextjs"},
}


def validate_plan(plan: ImplementationPlan, project_type: str) -> ImplementationPlan:
    allowed = _COMPATIBLE.get(project_type, set())
    cleaned: list[PlanStep] = []
    warnings: list[str] = []
    for step in plan.steps:
        blob = f"{step.title} {step.detail}".lower()
        blocked = _blocked_frameworks(blob, allowed)
        if blocked or _looks_like_foreign_install(blob, allowed):
            warnings.append(f"Rejected plan step that would introduce {', '.join(sorted(blocked) or ['a new framework'])}: {step.title}")
            continue
        cleaned.append(step)
    if not cleaned:
        cleaned = [
            PlanStep(index=1, title="Inspect existing code", detail="Read the current application files"),
            PlanStep(index=2, title="Apply a minimal fix", detail="Change only files required by the task"),
            PlanStep(index=3, title="Run tests", detail="pytest"),
        ]
    for idx, step in enumerate(cleaned, start=1):
        step.index = idx
    if warnings:
        plan.risks = list(plan.risks) + warnings
        plan.summary = (plan.summary or "").rstrip() + " (validated against existing architecture)"
    plan.steps = cleaned
    return plan


def _blocked_frameworks(text: str, allowed: set[str]) -> set[str]:
    found: set[str] = set()
    for name, aliases in _FRAMEWORKS.items():
        if any(alias in text for alias in aliases) and name not in allowed and not aliases & allowed:
            if re.search(rf"\b(install|add|introduce|migrate to|switch to)\b.*\b{name}\b", text) or re.search(
                rf"\b{name}\b.*\b(install|app|application|server)\b", text
            ):
                found.add(name)
    return found


def _looks_like_foreign_install(text: str, allowed: set[str]) -> bool:
    if "pip install" in text or "npm install" in text:
        for name in _FRAMEWORKS:
            if name in text and name not in allowed:
                return True
    return False
