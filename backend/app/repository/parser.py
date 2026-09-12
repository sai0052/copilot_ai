"""Lightweight source parsers for symbols and imports."""

from __future__ import annotations

import ast
import re
from pathlib import Path


def extract_python_symbols(source: str) -> dict[str, list[str]]:
    classes: list[str] = []
    functions: list[str] = []
    imports: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {
            "classes": _fallback_names(source, r"^class\s+(\w+)"),
            "functions": _fallback_names(source, r"^def\s+(\w+)"),
            "imports": _fallback_names(source, r"^(?:from\s+[\w.]+\s+import\s+.+|import\s+[\w.]+)"),
        }
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            functions.append(node.name)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = ", ".join(alias.name for alias in node.names)
            imports.append(f"from {module} import {names}".strip())
    return {"classes": classes, "functions": functions, "imports": imports}


def _fallback_names(source: str, pattern: str) -> list[str]:
    return re.findall(pattern, source, flags=re.M)


def parse_file(path: Path) -> dict[str, list[str]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if path.suffix == ".py":
        return extract_python_symbols(text)
    classes = re.findall(r"class\s+(\w+)", text)
    functions = re.findall(r"(?:function|const|let|var)\s+(\w+)", text)
    imports = re.findall(r"^(?:import\s+.+|from\s+.+import\s+.+)", text, flags=re.M)
    return {"classes": classes, "functions": functions, "imports": imports}
