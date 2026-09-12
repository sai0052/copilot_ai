"""Explicit LLM-callable tools with schemas and validation."""

from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel, Field, ValidationError

from app.llm.models import ToolSpec
from app.tools.filesystem import FileSystemTools
from app.tools.git import GitTool
from app.tools.search import SearchTool
from app.tools.terminal import TerminalTool
from app.tools.tests import TestRunner


class ListFilesInput(BaseModel):
    directory: str = "."
    glob: str = "*"


class ReadFileInput(BaseModel):
    path: str = Field(min_length=1)


class SearchCodeInput(BaseModel):
    query: str = Field(min_length=1)
    regex: bool = False
    mode: str = "text"
    filename: str | None = None


class WriteFileInput(BaseModel):
    path: str
    content: str


class PatchFileInput(BaseModel):
    path: str
    old: str
    new: str


class DeleteFileInput(BaseModel):
    path: str


class RunCommandInput(BaseModel):
    command: str = Field(min_length=1)


class RunTestsInput(BaseModel):
    extra_args: str = ""


class EmptyInput(BaseModel):
    pass


WRITE_TOOLS = {"write_file", "patch_file", "delete_file"}


class ToolRegistry:
    def __init__(self, root: str, mode: str = "implement") -> None:
        self.mode = mode
        fs = FileSystemTools(root)
        search = SearchTool(root)
        terminal = TerminalTool(root)
        tests = TestRunner(root)
        git = GitTool(root)
        self._handlers: dict[str, tuple[type[BaseModel], Callable[..., Any]]] = {
            "list_files": (ListFilesInput, lambda inp: {"files": fs.list_files(inp.directory, inp.glob)}),
            "read_file": (ReadFileInput, lambda inp: {"path": inp.path, "content": fs.read_file(inp.path)}),
            "search_code": (
                SearchCodeInput,
                lambda inp: {"hits": search.search_code(inp.query, inp.regex, inp.filename, inp.mode)},
            ),
            "write_file": (WriteFileInput, lambda inp: {"path": inp.path, "diff": fs.write_file(inp.path, inp.content)}),
            "patch_file": (PatchFileInput, lambda inp: {"path": inp.path, "diff": fs.patch_file(inp.path, inp.old, inp.new)}),
            "delete_file": (DeleteFileInput, lambda inp: {"path": inp.path, "diff": fs.delete_file(inp.path)}),
            "run_command": (RunCommandInput, lambda inp: terminal.run_command(inp.command)),
            "run_tests": (RunTestsInput, lambda inp: tests.run_tests(inp.extra_args)),
            "git_diff": (EmptyInput, lambda _inp: {"diff": git.diff()}),
            "git_status": (EmptyInput, lambda _inp: {"status": git.status()}),
        }
        self.fs = fs
        self.git = git
        self.tests = tests
        self.terminal = terminal

    def specs(self) -> list[ToolSpec]:
        descriptions = {
            "list_files": "List files in a repository directory.",
            "read_file": "Read a text file from the repository. Never guess file contents.",
            "search_code": "Search the repository. mode: text|regex|filename|symbol|imports.",
            "write_file": "Create or overwrite a text file with full contents.",
            "patch_file": "Replace a unique old snippet with new text in a file.",
            "delete_file": "Delete a file inside the repository.",
            "run_command": "Run an allowlisted command in the repository root.",
            "run_tests": "Run pytest in the repository.",
            "git_diff": "Show git diff for the repository.",
            "git_status": "Show git status for the repository.",
        }
        readonly = self.mode in {"review", "explain"}
        specs: list[ToolSpec] = []
        for name, (model, _handler) in self._handlers.items():
            if readonly and name in WRITE_TOOLS:
                continue
            specs.append(
                ToolSpec(
                    name=name,
                    description=descriptions[name],
                    parameters=model.model_json_schema(),
                )
            )
        return specs

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name not in self._handlers:
            return {"ok": False, "error": f"Unknown tool: {name}"}
        if self.mode in {"review", "explain"} and name in WRITE_TOOLS:
            return {"ok": False, "tool": name, "error": "Write tools are disabled in review/explain mode"}
        model, handler = self._handlers[name]
        try:
            parsed = model.model_validate(arguments)
            result = handler(parsed)
            return {"ok": True, "tool": name, "result": result}
        except ValidationError as exc:
            return {"ok": False, "tool": name, "error": str(exc)}
        except Exception as exc:  # noqa: BLE001 - tool failures must not crash the agent
            return {"ok": False, "tool": name, "error": str(exc)}
