from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "stockapp-backend"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    environment: str = "development"
    cors_origins: str = (
        "http://localhost:3000,"
        "http://localhost:5173,"
        "http://localhost:8080,"
        "http://127.0.0.1:3000,"
        "http://127.0.0.1:5173,"
        "http://127.0.0.1:8080"
    )
    pandaai_username: str = ""
    pandaai_password: str = ""
    pandaai_base_url: str = "http://pandadata.pandaaiquant.com"
    pandaai_timeout_seconds: float = Field(default=15.0, gt=0, le=120)
    pandaai_max_retries: int = Field(default=2, ge=1, le=10)
    pandaai_verify_ssl: bool = True
    pandaai_cache_ttl_seconds: int = Field(default=60, ge=1, le=86400)
    siliconflow_api_key: SecretStr | None = None
    siliconflow_base_url: str = "https://api.siliconflow.com/v1"
    siliconflow_model: str = Field(min_length=1)
    siliconflow_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    siliconflow_max_tokens: int = Field(default=512, ge=1, le=4096)
    newsapi_api_key: SecretStr | None = None
    newsapi_base_url: str = "https://newsapi.org/v2"
    newsapi_timeout_seconds: float = Field(default=15.0, gt=0, le=120)
    newsapi_default_language: str = Field(default="en", min_length=2, max_length=8)
    newsapi_default_page_size: int = Field(default=20, ge=1, le=100)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @field_validator("siliconflow_model")
    @classmethod
    def strip_siliconflow_model(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("SILICONFLOW_MODEL must not be blank")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
