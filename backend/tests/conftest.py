from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("LLM_API_KEY", "")
os.environ.setdefault("DATABASE_URL", "sqlite:///./data/test_codepilot.db")

Path("data").mkdir(exist_ok=True)


@pytest.fixture()
def client(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    from app.config import get_settings
    from app.database.database import Base, engine
    from app.main import create_app

    get_settings.cache_clear()
    Base.metadata.create_all(bind=engine)
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client

