"""
Security Pydantic schemas.

tenant_id is intentionally absent from every schema — it is derived from the
caller's JWT server-side (NULL for master-DB users), never sent in the request
or returned in the response.
"""
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict


class SecurityBase(BaseModel):
    # Single sign-on (SSO)
    enable_sso: bool = Field(default=False, description="Enable SSO for the client")

    # Multi-factor authentication (MFA)
    require_mfa: bool = Field(default=False, description="Require MFA at login")

    # Session & password policy
    session_timeout_min: Optional[int] = Field(None, ge=0, description="Session timeout (minutes)")
    idle_timeout_min: Optional[int] = Field(None, ge=0, description="Idle timeout (minutes)")
    max_concurrent_sessions: Optional[int] = Field(None, ge=0)
    remember_me_days: Optional[int] = Field(None, ge=0, description="Remember-me duration (days)")
    password_min_length: Optional[int] = Field(None, ge=0)
    password_expiry_days: Optional[int] = Field(None, ge=0)
    password_history: Optional[int] = Field(None, ge=0)
    require_complexity: bool = Field(default=True)
    lock_after_failed_logins: bool = Field(default=True)
    ip_allowlist: Optional[List[str]] = Field(default=None, description="Allowed CIDRs (one per line in the UI)")

    is_active: bool = Field(default=True)


class SecurityCreate(SecurityBase):
    pass


class SecurityUpdate(BaseModel):
    enable_sso: Optional[bool] = None
    require_mfa: Optional[bool] = None
    session_timeout_min: Optional[int] = Field(None, ge=0)
    idle_timeout_min: Optional[int] = Field(None, ge=0)
    max_concurrent_sessions: Optional[int] = Field(None, ge=0)
    remember_me_days: Optional[int] = Field(None, ge=0)
    password_min_length: Optional[int] = Field(None, ge=0)
    password_expiry_days: Optional[int] = Field(None, ge=0)
    password_history: Optional[int] = Field(None, ge=0)
    require_complexity: Optional[bool] = None
    lock_after_failed_logins: Optional[bool] = None
    ip_allowlist: Optional[List[str]] = None
    is_active: Optional[bool] = None


class SecurityResponse(SecurityBase):
    security_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SecurityListResponse(BaseModel):
    security: List[SecurityResponse]
    total: int
    page: int
    size: int
    pages: int
