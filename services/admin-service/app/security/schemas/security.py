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
    # Single sign-on (SSO) — sso_* fields apply only when enable_sso is true
    enable_sso: bool = Field(default=False, description="Enable SSO for the client")
    sso_provider: Optional[str] = Field(None, max_length=50, description="Identity provider (e.g. Okta, Azure AD, Google)")
    sso_entity_id: Optional[str] = Field(None, max_length=255, description="Entity ID / Issuer")
    sso_sign_in_url: Optional[str] = Field(None, max_length=500, description="Sign-in URL")
    sso_metadata_url: Optional[str] = Field(None, max_length=500, description="IdP metadata URL")
    sso_auto_provision_users: bool = Field(default=False, description="Auto-provision users on first SSO login")
    sso_force_for_all_users: bool = Field(default=False, description="Force SSO for all users (disables password login)")
    sso_signing_certificate: Optional[str] = Field(None, description="X.509 signing certificate (PEM)")

    # Multi-factor authentication (MFA) — mfa_* fields apply only when require_mfa is true
    require_mfa: bool = Field(default=False, description="Require MFA at login")
    mfa_allowed_methods: Optional[List[str]] = Field(default=None, description="Allowed MFA methods, e.g. ['totp', 'sms', 'email']")
    mfa_enforce_for: Optional[str] = Field(None, max_length=50, description="Scope MFA is enforced for (e.g. all_users, admins_only)")
    mfa_enrollment_grace_days: Optional[int] = Field(None, ge=0, description="Days a user has to enroll in MFA before it's enforced")

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
    lockout_threshold: Optional[int] = Field(None, ge=0, description="Failed login attempts before lockout")
    ip_allowlist: Optional[List[str]] = Field(default=None, description="Allowed CIDRs (one per line in the UI)")

    is_active: bool = Field(default=True)


class SecurityCreate(SecurityBase):
    pass


class SecurityUpdate(BaseModel):
    enable_sso: Optional[bool] = None
    sso_provider: Optional[str] = Field(None, max_length=50)
    sso_entity_id: Optional[str] = Field(None, max_length=255)
    sso_sign_in_url: Optional[str] = Field(None, max_length=500)
    sso_metadata_url: Optional[str] = Field(None, max_length=500)
    sso_auto_provision_users: Optional[bool] = None
    sso_force_for_all_users: Optional[bool] = None
    sso_signing_certificate: Optional[str] = None
    require_mfa: Optional[bool] = None
    mfa_allowed_methods: Optional[List[str]] = None
    mfa_enforce_for: Optional[str] = Field(None, max_length=50)
    mfa_enrollment_grace_days: Optional[int] = Field(None, ge=0)
    session_timeout_min: Optional[int] = Field(None, ge=0)
    idle_timeout_min: Optional[int] = Field(None, ge=0)
    max_concurrent_sessions: Optional[int] = Field(None, ge=0)
    remember_me_days: Optional[int] = Field(None, ge=0)
    password_min_length: Optional[int] = Field(None, ge=0)
    password_expiry_days: Optional[int] = Field(None, ge=0)
    password_history: Optional[int] = Field(None, ge=0)
    require_complexity: Optional[bool] = None
    lock_after_failed_logins: Optional[bool] = None
    lockout_threshold: Optional[int] = Field(None, ge=0)
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
