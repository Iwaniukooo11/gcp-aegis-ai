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
    slack_gateway_url: str
    slack_alert_channel_id: str = ""
    vertex_model: str = "gemini-1.5-flash"
    session_ttl_hours: int = 24
    receipt_ttl_hours: int = 24

    @field_validator("gcp_project", "gcp_region", "bigquery_dataset", "bigquery_incidents_table", "firestore_database", "slack_gateway_url")
    @classmethod
    def must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be empty")
        return v

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
