"""FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from app.database.database import get_db as _get_db


def get_db() -> Generator[Session, None, None]:
    yield from _get_db()
