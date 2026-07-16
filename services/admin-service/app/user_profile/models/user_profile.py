from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid


class UserProfile(Base):
    """
    Per-user UI / appearance preferences plus login-related flags.

    One row per user (``user_id`` is unique). Holds presentation settings
    (theme, accent colour, density, language, direction) alongside the
    ``can_change_password`` flag and the active ``session`` token.
    """
    __tablename__ = "user_profile"

    user_profile_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Owner of this profile (usersetup_basic.id). One profile per user.
    user_id = Column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    # Tenant scope (NULL for master-DB / platform users) — used for auditing.
    tenant_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    # Appearance preferences
    theme = Column(String(20), nullable=False, default="light", server_default="light")            # light | dark
    accent_color = Column(String(50), nullable=False, default="blue", server_default="blue")        # e.g. blue
    density = Column(String(20), nullable=False, default="comfortable", server_default="comfortable")  # compact | comfortable | spacious
    language = Column(String(50), nullable=False, default="English", server_default="English")       # e.g. English
    direction = Column(String(10), nullable=False, default="ltr", server_default="ltr")              # ltr | rtl

    # Login-related fields
    # Mirrors usersetup_basic.can_change_password — True → user is allowed to
    # change their own password; defaults to True.
    can_change_password = Column(Boolean, nullable=False, default=True, server_default="true")
    # Active session token / identifier for this user (nullable).
    session = Column(String(255), nullable=True)

    # Lifecycle / soft-delete
    is_active = Column(Boolean, default=True)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by = Column(UUID(as_uuid=True), nullable=True)
    updated_by = Column(UUID(as_uuid=True), nullable=True)

    def __repr__(self):
        return f"<UserProfile(id={self.user_profile_id}, user_id={self.user_id}, theme={self.theme})>"
