"""
Application configuration management's
"""
from pydantic_settings import BaseSettings
from typing import Optional
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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # AES-256-GCM field encryption key
    # base64url-encoded 32-byte key — generate with:
    #   python -c "import secrets,base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
    # If absent, key is derived from SECRET_KEY via HKDF (not recommended for production).
    ENCRYPTION_KEY: Optional[str] = None
    
    # JWT Public Key for RS256 verification (optional, for production)
    # If using RS256, provide the public key from the auth service
    JWT_PUBLIC_KEY: Optional[str] = None
    
    # Identity Service (external)
    IDENTITY_SERVICE_URL: Optional[str] = None

    # Audit Service (internal)
    AUDIT_SERVICE_URL: str = "http://audit-service:8000"
    
    # CORS
    CORS_ORIGINS: list = ["*"]
    
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
