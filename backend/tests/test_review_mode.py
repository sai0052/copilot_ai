from app.tools.registry import ToolRegistry


def test_review_mode_blocks_writes(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    tools = ToolRegistry(str(tmp_path), mode="review")
    result = tools.execute("write_file", {"path": "a.py", "content": "x = 2\n"})
    assert result["ok"] is False
    names = {spec.name for spec in tools.specs()}
    assert "write_file" not in names
    assert "read_file" in names
    assert (tmp_path / "a.py").read_text(encoding="utf-8") == "x = 1\n"
