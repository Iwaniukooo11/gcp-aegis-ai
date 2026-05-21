import os
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    gcp_project: str
    gcp_region: str
    environment: str = "dev"
    bigquery_dataset: str
    bigquery_incidents_table: str
    firestore_database: str
    vertex_model: str = "gemini-2.5-flash"
    allowed_client_project_ids: str = ""
    session_ttl_hours: int = 24

    @field_validator("gcp_project", "gcp_region", "bigquery_dataset", "bigquery_incidents_table", "firestore_database")
    @classmethod
    def must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be empty")
        return v

    def allowed_projects(self) -> list[str]:
        """Return the whitelist of client project IDs that may be queried."""
        return [p.strip() for p in self.allowed_client_project_ids.split(",") if p.strip()]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
