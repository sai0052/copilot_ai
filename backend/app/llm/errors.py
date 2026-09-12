"""LLM error types with user-safe messages (never include API keys)."""

from __future__ import annotations

from typing import Any


class LLMError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_type: str = "llm_error",
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_type = error_type
        self.retryable = retryable

    def to_public_dict(self) -> dict[str, Any]:
        return {"type": self.error_type, "message": str(self), "retryable": self.retryable}


class RateLimitError(LLMError):
    def __init__(
        self,
        message: str = "LLM rate limit reached. Please wait and try again.",
        *,
        retry_after: str | None = None,
        body: str = "",
    ) -> None:
        super().__init__(message, status_code=429, error_type="rate_limit", retryable=True)
        self.retry_after = retry_after
        self.body = body


class LLMCancelled(LLMError):
    def __init__(self) -> None:
        super().__init__("Agent cancelled", status_code=None, error_type="cancelled", retryable=False)


class AuthError(LLMError):
    def __init__(self, message: str = "LLM API key is invalid or expired.") -> None:
        super().__init__(message, status_code=401, error_type="auth", retryable=False)


class ForbiddenError(LLMError):
    def __init__(self, message: str = "Your Groq project does not have access to this model.") -> None:
        super().__init__(message, status_code=403, error_type="permission", retryable=False)


class ModelNotFoundError(LLMError):
    def __init__(self, message: str = "The configured LLM model was not found.") -> None:
        super().__init__(message, status_code=404, error_type="not_found", retryable=False)
