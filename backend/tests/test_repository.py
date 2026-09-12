from pathlib import Path

from app.repository.scanner import RepositoryScanner
from app.repository.search import CodeSearch


def test_scanner_detects_fastapi(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text("fastapi\nuvicorn\n", encoding="utf-8")
    (tmp_path / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    (tmp_path / "venv").mkdir()
    (tmp_path / "venv" / "ignored.py").write_text("x=1", encoding="utf-8")
    repo = RepositoryScanner().scan(tmp_path)
    assert repo.project_type == "fastapi"
    paths = {item.path for item in repo.files}
    assert "venv/ignored.py" not in paths
    assert any(item.path.endswith("test_main.py") for item in repo.files)


def test_search_text_and_symbol(tmp_path: Path):
    (tmp_path / "mod.py").write_text("class Auth:\n    def login(self):\n        return 1\n", encoding="utf-8")
    search = CodeSearch(tmp_path)
    hits = search.search("class Auth")
    assert hits
    symbols = search.search_symbols("Auth")
    assert symbols
    files = search.search_filename("mod.py")
    assert files[0]["path"] == "mod.py"
