from app.execution.command_policy import CommandDenied, validate_command
import pytest


def test_allow_pytest():
    tokens = validate_command("pytest -q")
    assert tokens[0] == "pytest"


def test_block_rm():
    with pytest.raises(CommandDenied):
        validate_command("rm -rf /")


def test_block_unknown_binary():
    with pytest.raises(CommandDenied):
        validate_command("format C:")


def test_block_git_force():
    with pytest.raises(CommandDenied):
        validate_command("git checkout --force main")


def test_block_env_dump():
    with pytest.raises(CommandDenied):
        validate_command("printenv")
