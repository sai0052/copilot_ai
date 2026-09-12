"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_KEYS = {
    "",
    "your_api_key_here",
    "changeme",
    "xxx",
    "replace_me",
}


def env_files() -> tuple[str, ...]:
    """Resolve .env paths from the repo root and backend dir, independent of cwd."""
    here = Path(__file__).resolve()
    backend_dir = here.parents[1]
    repo_root = here.parents[2]
    files = [path for path in (repo_root / ".env", backend_dir / ".env") if path.is_file()]
    return tuple(str(path) for path in files)


class Settings(BaseSettings):
    """Runtime settings for CodePilot AI.

    Environment variable names match field names in uppercase (LLM_MODEL, etc.).
    Aliases are avoided so pydantic-settings reads dotenv keys reliably.
    """

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    llm_api_key: str = Field(default="")
    llm_base_url: str = Field(default="https://api.groq.com/openai/v1")
    llm_model: str = Field(default="openai/gpt-oss-120b")
    llm_timeout_seconds: float = Field(default=90.0)
    llm_max_tokens: int = Field(default=2048)
    llm_temperature: float = Field(default=0.2)
    llm_max_retries: int = Field(default=3)
    llm_retry_base_seconds: float = Field(default=5.0)
    llm_retry_jitter: float = Field(default=0.15)
    llm_max_context_tokens: int | None = Field(default=None)

    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8010)
    app_cors_origins: str = Field(
        default=(
            "http://localhost:5173,http://127.0.0.1:5173,"
            "http://localhost:5174,http://127.0.0.1:5174,"
            "http://localhost:8080,http://127.0.0.1:8080"
        )
    )
    database_url: str = Field(default="sqlite:///./data/codepilot.db")
    log_level: str = Field(default="INFO")

    agent_max_iterations: int = Field(default=5)
    agent_max_tool_rounds: int = Field(default=10)
    agent_task_timeout_seconds: float = Field(default=300.0)
    agent_require_git_branch: bool = Field(default=True)
    agent_show_diff_before_approve: bool = Field(default=False)
    context_max_tokens: int = Field(default=8000)
    file_max_bytes: int = Field(default=1_048_576)
    command_timeout_seconds: float = Field(default=120.0)
    command_output_max_bytes: int = Field(default=200_000)
    allowed_commands: str = Field(default="pytest,python,python3,pip,pip3,npm,npx,node,git")

    embeddings_enabled: bool = Field(default=False)
    embeddings_provider: str = Field(default="sentence_transformers")
    embeddings_model: str = Field(default="all-MiniLM-L6-v2")

    data_dir: Path = Field(default=Path("./data"))
    import_max_files: int = Field(default=2000)
    import_max_file_bytes: int = Field(default=1_048_576)
    import_max_repo_bytes: int = Field(default=52_428_800)

    @field_validator("llm_api_key", "llm_model", "llm_base_url", mode="before")
    @classmethod
    def _strip_text(cls, value: object) -> str:
        return str(value or "").strip()

    @model_validator(mode="after")
    def _apply_context_alias(self) -> Settings:
        if self.llm_max_context_tokens is not None:
            self.context_max_tokens = int(self.llm_max_context_tokens)
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.app_cors_origins.split(",") if item.strip()]

    @property
    def allowed_command_list(self) -> list[str]:
        return [item.strip().lower() for item in self.allowed_commands.split(",") if item.strip()]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def llm_configured(self) -> bool:
        key = self.llm_api_key.strip()
        return bool(key) and key.lower() not in _PLACEHOLDER_KEYS

    @property
    def llm_is_configured(self) -> bool:
        return bool(self.llm_configured)

    @property
    def env_files_present(self) -> bool:
        return bool(env_files())


@lru_cache
def get_settings() -> Settings:
    """Load settings from process env and discovered .env files. Cached per process."""
    settings = Settings(_env_file=env_files() or None)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings
