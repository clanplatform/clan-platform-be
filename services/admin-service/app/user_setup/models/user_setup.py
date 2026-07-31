from sqlalchemy import Column, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid


class UserSetup(Base):
    """
    Main user setup table (parent table).
    Contains the primary key that all child tables reference.
    """
    __tablename__ = "user_setup"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Child relationships
    basic = relationship("UserSetupBasic", back_populates="user_setup", cascade="all, delete-orphan", uselist=False)
    preferences = relationship("UserSetupPreference", back_populates="user_setup", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<UserSetup(id={self.id})>"


class UserSetupBasic(Base):
    """
    Basic user setup information table (child table 1).
    Stores fundamental user details like name, employee info, contact, department, etc.
    References user_setup.id as foreign key.
    """
    __tablename__ = "usersetup_basic"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_setup_id = Column(UUID(as_uuid=True), ForeignKey("user_setup.id", ondelete="CASCADE"), nullable=False, unique=True)

    # Personal Information
    firstname = Column(String(100), nullable=False)
    lastname = Column(String(100), nullable=False)
    employee_id = Column(String(50), nullable=False, unique=True)
    username = Column(String(100), nullable=False, unique=True)
    email = Column(String(255), nullable=False, unique=True)
    phone_number = Column(String(20), nullable=True)
    password_hash = Column(String(255), nullable=False)  # Hashed password
    password_changed = Column(DateTime(timezone=True), nullable=True)  # Last password change timestamp
    is_password_change = Column(Boolean, default=False, nullable=False)  # Flag to indicate if user needs to change password
    # True → first-login password-change flow applies; False → user logs
    # straight in and is redirected to the tenant's application.
    can_change_password = Column(Boolean, default=True, server_default='true', nullable=False)

    # Employment Status
    status = Column(String(50), nullable=False, default='active')  # active, inactive, suspended, etc.

    # Entity Access — entities is a backend fallback array read by audit context
    # resolution (get_audit_org_context); default_entity ("Branch / location")
    # is the single source of truth exposed via the schema.
    entities = Column(ARRAY(UUID(as_uuid=True)), nullable=True)  # Array of entity IDs
    default_entity = Column(UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=True)

    # Role assignment — single role (user_role.id), the source of truth for
    # this user's role. Replaces the old usersetup_roles_entity table.
    role_id = Column(UUID(as_uuid=True), ForeignKey("user_role.id"), nullable=True)

    # User group (bare reference — no user_groups table yet) + invite email flag
    user_group_id = Column(UUID(as_uuid=True), nullable=True)
    send_invite_email = Column(Boolean, nullable=False, server_default='false', default=False)

    # Tenant — derived from the JWT server-side, never accepted/returned in the
    # CRUD schema (NULL = master-DB user, a tenant UUID = tenant-DB user).
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.tenant_id"), nullable=True, index=True)

    # Allowed origins for master-DB users (tenant_id NULL) — tenant users get
    # theirs from tenants.allowed_origins; this is the per-user equivalent
    # (e.g. post-login redirect target for platform users).
    allowed_origins = Column(ARRAY(Text()), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user_setup = relationship("UserSetup", back_populates="basic")
    tenant = relationship("Tenant", foreign_keys=[tenant_id])
    default_entity_rel = relationship("Entity", foreign_keys=[default_entity])
    role = relationship("UserRoleMain", foreign_keys=[role_id])

    def __repr__(self):
        return f"<UserSetupBasic(id={self.id}, user_setup_id={self.user_setup_id}, username={self.username}, email={self.email}, status={self.status})>"

    def is_admin(self) -> bool:
        """Check if user is admin based on the assigned role"""
        # Check if email contains 'admin' (for development/testing)
        if self.email and 'admin' in self.email.lower():
            return True

        if not self.role_id:
            return False

        from app.user_role.models.user_role import UserRoleBasic
        from app.infrastructure.database.session import SessionLocal

        db = SessionLocal()
        try:
            admin_role = db.query(UserRoleBasic).filter(
                UserRoleBasic.user_role_id == self.role_id,
                UserRoleBasic.is_admin == True,
                UserRoleBasic.active == True
            ).first()
            return admin_role is not None
        finally:
            db.close()


class UserSetupPreference(Base):
    """
    User setup preferences table (child table 2).
    Stores user preferences like language, timezone, and theme.
    References user_setup.id and usersetup_basic.id as foreign keys.
    """
    __tablename__ = "usersetup_preference"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_setup_id = Column(UUID(as_uuid=True), ForeignKey("user_setup.id", ondelete="CASCADE"), nullable=False)
    usersetup_basic_id = Column(UUID(as_uuid=True), ForeignKey("usersetup_basic.id", ondelete="CASCADE"), nullable=False)

    # User Preferences
    language = Column(String(10), nullable=False, default='en')  # e.g., 'en', 'es', 'fr'
    timezone = Column(String(50), nullable=False, default='UTC')  # e.g., 'America/New_York', 'UTC'
    theme = Column(String(20), nullable=False, default='light')  # e.g., 'light', 'dark', 'auto'
    accent_color = Column(String(50), nullable=False, default='blue', server_default='blue')  # e.g., 'blue'
    density = Column(String(20), nullable=False, default='comfortable', server_default='comfortable')  # compact | comfortable | spacious

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user_setup = relationship("UserSetup", back_populates="preferences")
    usersetup_basic = relationship("UserSetupBasic", backref="preferences")

    def __repr__(self):
        return f"<UserSetupPreference(id={self.id}, user_setup_id={self.user_setup_id}, language={self.language}, timezone={self.timezone}, theme={self.theme})>"

