"""
Application configuration management's
"""
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Any, List, Optional
from functools import lru_cache
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Application
    APP_NAME: str = "Admin Service"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "Platform Admin Service for managing domains and applications"
    DEBUG: bool = False

    # Database - PostgreSQL
    DATABASE_URL: str

    # Redis Cache
    REDIS_URL: str
    CACHE_DEFAULT_TTL: int = 10  # 10  seconds

    # MongoDB
    MONGODB_URL: str
    MONGODB_DB_NAME: str = "clan_platform"

    # Security
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: Optional[str] = None      # e.g. "clan-identity" — validates iss claim
    JWT_AUDIENCE: Optional[str] = None    # e.g. "api-gateway"  — validates aud claim
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # AES-256-GCM field encryption key
    # base64url-encoded 32-byte key — generate with:
    #   python -c "import secrets,base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
    # If absent, key is derived from SECRET_KEY via HKDF (not recommended for production).
    ENCRYPTION_KEY: Optional[str] = None

    # RS256 public key — two mutually exclusive sources (first wins):
    #   JWT_PUBLIC_KEY : PEM string set in .env.prod (production)
    #   JWKS_URI       : auto-fetched in local dev via clan-network
    JWT_PUBLIC_KEY: Optional[str] = None
    JWKS_URI: Optional[str] = None

    # Identity Service (external)
    IDENTITY_SERVICE_URL: Optional[str] = None

    # Audit Service (internal)
    AUDIT_SERVICE_URL: str = "http://audit-service:8000"

    # Tenant Portal Service (internal sync)
    TENANT_PORTAL_SERVICE_URL: str = "http://tenant-portal-service:8000"
    INTERNAL_API_KEY: str = "internal-secret-key"

    # Communication email-service (clan-communication-be, published on host port 9001)
    EMAIL_SERVICE_URL: str = "http://host.docker.internal:9001"

    # CORS
    CORS_ORIGINS: List[str] = ["*"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> Any:
        """Accept JSON array string, comma-separated string, or empty → default ['*']."""
        if not v or v == "":
            return ["*"]
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                import json
                return json.loads(v)
            # comma-separated: "https://a.com,https://b.com"
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # Kafka (optional)
    KAFKA_BOOTSTRAP_SERVERS: Optional[str] = None
    KAFKA_TOPIC_PREFIX: str = "admin-service"

    class Config:
        # Path to .env.local in config/environments directory (relative to project root)
        env_file = Path(__file__).parent.parent.parent.parent.parent / "config" / "environments" / ".env.local"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields in .env file


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Uses lru_cache to ensure settings are loaded only once.
    """
    return Settings()


# Global settings instance
settings = get_settings()
