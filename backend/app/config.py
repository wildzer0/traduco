"""Application settings, read from environment variables prefixed with ``TRADUCO_``."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRADUCO_", env_file=".env", extra="ignore")

    workspaces_dir: Path = Path("~/Traduco")
    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = "gemma4:e4b"
    llm_api_key: str = ""
    # Built frontend served by the backend; ``None`` disables static serving.
    frontend_dist: Path | None = None
    # Demo project offered by "Open example"; defaults to <repo>/examples/progetto-esempio.
    examples_dir: Path | None = None
    version: str = "0.1.0"

    @property
    def example_project(self) -> Path | None:
        base = self.examples_dir or Path(__file__).resolve().parents[2] / "examples"
        example = base / "progetto-esempio"
        return example if (example / "progetto.yaml").is_file() else None

    @property
    def skeletons_dir(self) -> Path:
        base = self.examples_dir or Path(__file__).resolve().parents[2] / "examples"
        return base / "scheletri"

    @property
    def workspaces_path(self) -> Path:
        return self.workspaces_dir.expanduser()


@lru_cache
def get_settings() -> Settings:
    return Settings()
