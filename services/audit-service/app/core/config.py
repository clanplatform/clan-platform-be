from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache
from pathlib import Path


class Settings(BaseSettings):
    APP_NAME: str = "Audit Service"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "Audit log service — records and queries all user-driven changes"
    DEBUG: bool = False

    DATABASE_URL: str
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_PUBLIC_KEY: Optional[str] = None
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    CORS_ORIGINS: list = ["*"]

    class Config:
        env_file = Path(__file__).parent.parent.parent.parent.parent / "config" / "environments" / ".env.local"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
