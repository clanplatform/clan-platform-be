from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid


class Security(Base):
    """
    A tenant's security configuration: SSO, MFA and session / password policy —
    the onboarding "Security" step.
    """
    __tablename__ = "security"

    security_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    # Derived from the JWT (never accepted/returned in the CRUD schema):
    #   NULL     -> master-DB user (token has no tenant_id)
    #   a tenant -> tenant-DB user (token's tenant_id)
    # Nullable so master-DB users can create rows in the master DB.
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.tenant_id"), nullable=True, index=True)

    # Single sign-on (SSO)
    enable_sso = Column(Boolean, nullable=False, server_default='false', default=False)

    # Multi-factor authentication (MFA)
    require_mfa = Column(Boolean, nullable=False, server_default='false', default=False)

    # Session & password policy
    session_timeout_min = Column(Integer, nullable=True)
    idle_timeout_min = Column(Integer, nullable=True)
    max_concurrent_sessions = Column(Integer, nullable=True)
    remember_me_days = Column(Integer, nullable=True)
    password_min_length = Column(Integer, nullable=True)
    password_expiry_days = Column(Integer, nullable=True)
    password_history = Column(Integer, nullable=True)
    require_complexity = Column(Boolean, nullable=False, server_default='true', default=True)
    lock_after_failed_logins = Column(Boolean, nullable=False, server_default='true', default=True)
    ip_allowlist = Column(ARRAY(Text), nullable=True)   # list of CIDRs (one per line in the UI)

    is_active = Column(Boolean, nullable=False, server_default='true', default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(UUID(as_uuid=True), nullable=True)

    def __repr__(self):
        return f"<Security(id={self.security_id}, tenant_id={self.tenant_id}, sso={self.enable_sso}, mfa={self.require_mfa})>"
