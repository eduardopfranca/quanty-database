"""
Worker configuration.

Loads environment variables from .env file at the project root using
pydantic-settings. Validates required values at boot and creates
data/log directories if missing.
"""
from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Project root is 4 levels up from this file:
# src/config.py -> src -> worker -> apps -> <repo root>
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class Settings(BaseSettings):
    """Worker runtime settings loaded from .env at the repo root."""

    # External services
    varos_api_key: str = Field(..., description="API key for Varos provider")
    supabase_url: str = Field(..., description="Supabase project URL")
    supabase_service_role_key: str = Field(..., description="Supabase service role key")

    # Worker
    worker_secret: str = Field(..., description="Shared secret for worker API auth")
    worker_data_dir: Path = Field(..., description="Local folder where parquet files are written")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_dir: Path = Field(default=Path("./logs"), description="Directory for log files")

    model_config = SettingsConfigDict(
        env_file=_REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("worker_data_dir", "log_dir", mode="after")
    @classmethod
    def _ensure_dir_exists(cls, value: Path) -> Path:
        """Create directory if it does not exist."""
        value.mkdir(parents=True, exist_ok=True)
        return value


settings = Settings()


if __name__ == "__main__":
    def _mask(value: str) -> str:
        if not value or len(value) < 8:
            return "***"
        return f"{value[:4]}...{value[-4:]}"

    print("Worker settings loaded:\n")
    print(f"  varos_api_key:             {_mask(settings.varos_api_key)}")
    print(f"  supabase_url:              {settings.supabase_url}")
    print(f"  supabase_service_role_key: {_mask(settings.supabase_service_role_key)}")
    print(f"  worker_secret:             {_mask(settings.worker_secret)}")
    print(f"  worker_data_dir:           {settings.worker_data_dir}")
    print(f"  log_level:                 {settings.log_level}")
    print(f"  log_dir:                   {settings.log_dir}")