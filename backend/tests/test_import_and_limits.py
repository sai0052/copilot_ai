from pathlib import Path

import pytest

from app.config import Settings
from app.repository.importer import import_files_to_workspace
from app.repository.scanner import RepositoryScanner
from app.utils.security import SecurityError, is_blocked_system_path, sanitize_relative_path


def test_import_preserves_nested_structure(tmp_path: Path):
    settings = Settings.model_construct(
        data_dir=tmp_path,
        import_max_files=50,
        import_max_file_bytes=10_000,
        import_max_repo_bytes=100_000,
    )
    root = import_files_to_workspace(
        "my-project",
        [
            ("app/main.py", "print(1)\n"),
            ("app/routes/users.py", "x=1\n"),
            ("tests/test_users.py", "def test_ok():\n    assert True\n"),
            ("requirements.txt", "fastapi\n"),
        ],
        settings=settings,
    )
    assert (root / "app" / "main.py").is_file()
    assert (root / "app" / "routes" / "users.py").is_file()
    assert (root / "tests" / "test_users.py").is_file()
    assert (root / "requirements.txt").is_file()
    scanned = RepositoryScanner().scan(root)
    paths = {item.path for item in scanned.files}
    assert "app/main.py" in paths
    assert "app/routes/users.py" in paths


def test_import_rejects_path_traversal(tmp_path: Path):
    settings = Settings.model_construct(
        data_dir=tmp_path,
        import_max_files=10,
        import_max_file_bytes=1000,
        import_max_repo_bytes=10_000,
    )
    with pytest.raises(SecurityError):
        import_files_to_workspace("bad", [("../../etc/passwd", "root\n")], settings=settings)
    with pytest.raises(SecurityError):
        sanitize_relative_path("..\\..\\Windows\\System32\\config")


def test_import_skips_secrets(tmp_path: Path):
    settings = Settings.model_construct(
        data_dir=tmp_path,
        import_max_files=10,
        import_max_file_bytes=1000,
        import_max_repo_bytes=10_000,
    )
    root = import_files_to_workspace(
        "sec",
        [(".env", "LLM_API_KEY=secret"), ("app.py", "print(1)\n")],
        settings=settings,
    )
    assert not (root / ".env").exists()
    assert (root / "app.py").exists()


def test_import_file_and_repo_limits(tmp_path: Path):
    settings = Settings.model_construct(
        data_dir=tmp_path,
        import_max_files=1,
        import_max_file_bytes=20,
        import_max_repo_bytes=30,
    )
    with pytest.raises(SecurityError, match="too many files"):
        import_files_to_workspace("n", [("a.py", "x"), ("b.py", "y")], settings=settings)
    settings.import_max_files = 10
    with pytest.raises(SecurityError, match="size limit"):
        import_files_to_workspace("n", [("a.py", "x" * 50)], settings=settings)
    settings.import_max_file_bytes = 1000
    with pytest.raises(SecurityError, match="size limit"):
        import_files_to_workspace("n", [("a.py", "x" * 40), ("b.py", "y" * 40)], settings=settings)


def test_blocked_system_paths():
    assert is_blocked_system_path(Path("/etc"))
    assert is_blocked_system_path(Path("C:/Windows"))


def test_detect_react_vite(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"dependencies":{"react":"18"},"devDependencies":{"vite":"6"}}', encoding="utf-8")
    (tmp_path / "vite.config.ts").write_text("export default {}\n", encoding="utf-8")
    assert RepositoryScanner().scan(tmp_path).project_type == "react_vite"


def test_detect_flask_and_django(tmp_path: Path):
    flask = tmp_path / "flask"
    flask.mkdir()
    (flask / "requirements.txt").write_text("flask\n", encoding="utf-8")
    (flask / "app.py").write_text("from flask import Flask\n", encoding="utf-8")
    django = tmp_path / "django"
    django.mkdir()
    (django / "manage.py").write_text("print('django')\n", encoding="utf-8")
    (django / "app.py").write_text("x=1\n", encoding="utf-8")
    assert RepositoryScanner().scan(flask).project_type == "flask"
    assert RepositoryScanner().scan(django).project_type == "django"
