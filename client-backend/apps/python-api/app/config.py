from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = Field(default="python-api", validation_alias="SERVICE_NAME")
    client_project_id: str = Field(default="aegis-client-420", validation_alias="CLIENT_PROJECT_ID")
    environment: str = Field(default="local", validation_alias="ENVIRONMENT")
    team: str = Field(default="demo", validation_alias="TEAM")
    version: str = Field(default="0.1.0", validation_alias="VERSION")

    chaos_enabled: bool = Field(default=True, validation_alias="CHAOS_ENABLED")
    chaos_auto_mode: bool = Field(default=False, validation_alias="CHAOS_AUTO_MODE")
    allow_destructive_chaos: bool = Field(default=False, validation_alias="ALLOW_DESTRUCTIVE_CHAOS")
    java_api_base_url: str = Field(default="http://java-api:8080", validation_alias="JAVA_API_BASE_URL")
    java_api_timeout_ms: int = Field(default=1000, validation_alias="JAVA_API_TIMEOUT_MS")

    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
