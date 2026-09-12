from pathlib import Path

from app.tools.tests import TestRunner


def test_runner_parses_pytest(tmp_path: Path):
    (tmp_path / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    result = TestRunner(tmp_path).run_tests()
    assert result["exit_code"] == 0
    assert result["passed"] >= 1
