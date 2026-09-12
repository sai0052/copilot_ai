"""Health and metrics endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app import __version__
from app.config import get_settings
from app.utils.metrics import snapshot

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "service": "codepilot-ai",
        "version": __version__,
        "model": settings.llm_model,
        "llm_configured": settings.llm_is_configured,
        "llm_base_url": settings.llm_base_url,
        "env_loaded": settings.env_files_present,
    }


@router.get("/metrics")
def metrics() -> dict:
    return snapshot()
