"""CodePilot AI FastAPI application."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import agent, files, health, projects
from app.api.validation import request_validation_handler
from app.config import get_settings
from app.database.database import init_db
from app.utils.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    init_db()
    settings = get_settings()
    application = FastAPI(
        title="CodePilot AI",
        description="Autonomous AI Coding Agent for Repository-Level Software Engineering",
        version="1.0.0",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1):\d+",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(health.router)
    application.include_router(projects.router)
    application.include_router(files.router)
    application.include_router(agent.router)
    application.add_exception_handler(RequestValidationError, request_validation_handler)
    return application


app = create_app()
