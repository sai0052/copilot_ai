from __future__ import annotations

import pytest

from app.execution.command_policy import CommandDenied, validate_command
from app.tools.filesystem import FileSystemTools
from app.utils.security import SecurityError, resolve_inside_repo


def test_path_traversal_blocked(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (tmp_path / "secret.txt").write_text("nope", encoding="utf-8")
    with pytest.raises(SecurityError):
        resolve_inside_repo(repo, "../secret.txt")


def test_secret_file_blocked(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".env").write_text("LLM_API_KEY=abc", encoding="utf-8")
    fs = FileSystemTools(repo)
    with pytest.raises(SecurityError):
        fs.read_file(".env")


def test_write_and_patch(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    fs = FileSystemTools(repo)
    fs.write_file("hello.py", "x = 1\n")
    fs.patch_file("hello.py", "x = 1", "x = 2")
    assert fs.read_file("hello.py") == "x = 2\n"


def test_python_syntax_validation(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    fs = FileSystemTools(repo)
    with pytest.raises(SyntaxError):
        fs.write_file("bad.py", "def oops(:\n")
