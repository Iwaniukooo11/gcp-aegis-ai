from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration for Slack Gateway.

    No Firestore, BigQuery, Vertex, or Monitoring — this service is a thin
    HTTP relay between Slack and internal Cloud Run services.
    """

    slack_bot_token: str
    slack_signing_secret: str
    query_processor_url: str
    default_slack_channel_id: str
    internal_alert_allowed_service_account: str
    incident_analyzer_url: str = ""
    environment: str = "dev"

    @field_validator(
        "slack_bot_token",
        "slack_signing_secret",
        "query_processor_url",
        "default_slack_channel_id",
        "internal_alert_allowed_service_account",
    )
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
