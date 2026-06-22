from sqlalchemy import Column, String, DateTime, Text, Boolean, ForeignKey, Integer, Time, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid


class UserRoleMain(Base):
    """
    Main user role table (parent table).
    Contains the primary key that all child tables reference.
    Note: Named UserRoleMain to avoid conflict with UserRole association table.
    """
    __tablename__ = "user_role"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Child relationships
    basic = relationship("UserRoleBasic", back_populates="user_role_main", cascade="all, delete-orphan", uselist=False)
    permissions = relationship("UserRolePermission", back_populates="user_role_main", cascade="all, delete-orphan")
    conditionals = relationship("UserRoleConditional", back_populates="user_role_main", cascade="all, delete-orphan")
    form_permissions = relationship("RoleFormPermission", back_populates="user_role", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<UserRoleMain(id={self.id})>"


class UserRoleBasic(Base):
    """
    Basic user role information table (child table 1).
    Stores fundamental role details like name, code, description, level, etc.
    References user_role.id as foreign key.
    """
    __tablename__ = "userrole_basic"
    __table_args__ = (
        UniqueConstraint('client_id', 'role_name', name='uq_userrole_basic_client_role_name'),
        UniqueConstraint('client_id', 'role_code', name='uq_userrole_basic_client_role_code'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_role_id = Column(UUID(as_uuid=True), ForeignKey("user_role.id", ondelete="CASCADE"), nullable=False, unique=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.client_id", ondelete="SET NULL"), nullable=True, index=True)

    role_name = Column(String(100), nullable=False)
    role_code = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    role_level = Column(Integer, nullable=False, default=1)
    system_role = Column(Boolean, default=False, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)  # Admin role flag
    active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user_role_main = relationship("UserRoleMain", back_populates="basic")
    form_permissions = relationship("RoleFormPermission", back_populates="userrole_basic", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<UserRoleBasic(id={self.id}, role_name={self.role_name}, role_code={self.role_code}, active={self.active})>"


class UserRolePermission(Base):
    """
    User role permissions table (child table 2).
    Stores menu permissions only. Form permissions are now handled in role_form_permission table.
    References user_role.id as foreign key and userrole_basic.id as foreign key.
    
    JSONB Format: [{"id": "uuid", "access": ["read", "write"]}, ...]
    """
    __tablename__ = "userrole_permission"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_role_id = Column(UUID(as_uuid=True), ForeignKey("user_role.id", ondelete="CASCADE"), nullable=False)
    userrole_basic_id = Column(UUID(as_uuid=True), ForeignKey("userrole_basic.id", ondelete="CASCADE"), nullable=False)

    # Menu permissions stored as JSONB
    # Format: [{"id": "uuid", "access": ["read", "write"]}, ...]
    menu_permissions = Column(postgresql.JSONB, nullable=False, default=[], server_default='[]')

    # Menu access level
    menu_access = Column(String(50), nullable=True, default='disable')

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user_role_main = relationship("UserRoleMain", back_populates="permissions")
    userrole_basic = relationship("UserRoleBasic", backref="permissions")
    role_form_permissions = relationship("RoleFormPermission", back_populates="userrole_permission", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<UserRolePermission(id={self.id}, userrole_basic_id={self.userrole_basic_id}, menu_access={self.menu_access})>"


class UserRoleConditional(Base):
    """
    User role conditional access table (child table 3).
    Stores time-based and IP-based access restrictions for user roles.
    References user_role.id, userrole_permission.id, and userrole_basic.id as foreign keys.
    """
    __tablename__ = "userrole_conditional"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_role_id = Column(UUID(as_uuid=True), ForeignKey("user_role.id", ondelete="CASCADE"), nullable=False)
    userrole_permission_id = Column(UUID(as_uuid=True), ForeignKey("userrole_permission.id", ondelete="CASCADE"), nullable=False)
    userrole_basic_id = Column(UUID(as_uuid=True), ForeignKey("userrole_basic.id", ondelete="CASCADE"), nullable=False)

    # Time-based restrictions
    enable_time = Column(Boolean, default=False, nullable=False)
    allowtime_start = Column(Time, nullable=True)
    allowtime_end = Column(Time, nullable=True)
    allow_days = Column(ARRAY(String), nullable=True)  # Array of day names: ['Monday', 'Tuesday', ...]

    # IP-based restrictions
    ip_restric = Column(Boolean, default=False, nullable=False)  # Enable IP restriction
    aip = Column(String(45), nullable=True)  # IP address A (supports IPv4 and IPv6)
    bip = Column(String(45), nullable=True)  # IP address B (for range)

    # Other restrictions
    enable_restric = Column(Boolean, default=False, nullable=False)  # General restriction enable flag
    required_reg = Column(Boolean, default=False, nullable=False)  # Require registration

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user_role_main = relationship("UserRoleMain", back_populates="conditionals")
    userrole_permission = relationship("UserRolePermission", backref="conditionals")
    userrole_basic = relationship("UserRoleBasic", backref="conditionals")

    def __repr__(self):
        return f"<UserRoleConditional(id={self.id}, user_role_id={self.user_role_id}, enable_time={self.enable_time}, ip_restric={self.ip_restric})>"

