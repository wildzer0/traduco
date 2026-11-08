"""Application settings, read from environment variables prefixed with ``TRADUCO_``."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRADUCO_", env_file=".env", extra="ignore")

    workspaces_dir: Path = Path("~/Traduco")
    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = "gemma4:e4b"
    llm_api_key: str = ""
    # Address of the author's own LanguageTool server; empty = spelling check off (RF-16).
    languagetool_url: str = ""
    # "desktop": one user on localhost, no login (default). "team": OIDC login, roles, locks, audit.
    mode: Literal["desktop", "team"] = "desktop"
    oidc_issuer: str = ""  # e.g. https://keycloak.example/realms/traduco
    oidc_client_id: str = "traduco"
    oidc_client_secret: str = ""
    oidc_scopes: str = "openid profile email"
    # Where the roles are in the ID token: a dotted path, e.g. "roles" or "realm_access.roles".
    oidc_roles_claim: str = "roles"
    # Role given to a user the identity provider sends without any of ours; empty = refuse them.
    oidc_default_role: str = ""
    session_secret: str = ""  # signs the session cookie; required in team mode
    session_hours: int = 12
    public_url: str = ""  # how browsers reach the app (redirect address); default: from the request
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
