"""Application settings; secrets are never embedded in source."""

from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    log_hmac_secret: SecretStr
    app_env: str = "production"
    db_pool_size: int = Field(default=5, ge=1, le=100)
    db_max_overflow: int = Field(default=5, ge=0, le=100)
    db_pool_timeout: float = Field(default=10, gt=0)
    db_pool_pre_ping: bool = True
    redis_connect_timeout: float = Field(default=1, gt=0)
    redis_socket_timeout: float = Field(default=1, gt=0)
    redis_bucket_limit_size: str = Field(default="8")
    redis_bucket_speed_size: float = Field(default=5.0, gt=0)

    @field_validator("log_hmac_secret")
    @classmethod
    def check_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("LOG_HMAC_SECRET must contain at least 32 characters")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings.model_validate({})
