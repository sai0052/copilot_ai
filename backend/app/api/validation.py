"""User-safe API validation errors (no stack traces, no secrets)."""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

PROMPT_TOO_SHORT = "Task must contain at least 3 characters."


def _is_prompt_length_error(errors: list[dict[str, Any]]) -> bool:
    for item in errors:
        loc = item.get("loc") or ()
        names = {str(part) for part in loc}
        err_type = str(item.get("type") or "")
        if names & {"prompt", "task"} and err_type in {"string_too_short", "missing", "value_error.any_str.min_length"}:
            return True
    return False


async def request_validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    if _is_prompt_length_error(errors):
        return JSONResponse(
            status_code=422,
            content={
                "error": "validation_error",
                "field": "prompt",
                "message": PROMPT_TOO_SHORT,
                "detail": PROMPT_TOO_SHORT,
            },
        )
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "field": None,
            "message": "Invalid request.",
            "detail": errors,
        },
    )
