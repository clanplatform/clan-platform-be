from sqlalchemy import Column, String, DateTime, Text, Boolean, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
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
        UniqueConstraint('tenant_id', 'role_name', name='uq_userrole_basic_tenant_role_name'),
        UniqueConstraint('tenant_id', 'role_code', name='uq_userrole_basic_tenant_role_code'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_role_id = Column(UUID(as_uuid=True), ForeignKey("user_role.id", ondelete="CASCADE"), nullable=False, unique=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=True, index=True)

    role_name = Column(String(100), nullable=False)
    role_code = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    role_level = Column(Integer, nullable=False, default=1)
    parent_role_id = Column(UUID(as_uuid=True), nullable=True)   # user_role.id of the parent role (Reports to)
    # What this role's permissions apply against: whole_organization,
    # branch_entity, department, or division. Enforced at the API layer
    # (see ACCESS_SCOPE_VALUES in schemas/user_role.py).
    access_scope = Column(String(50), nullable=True)
    is_admin = Column(Boolean, default=False, nullable=False)  # Admin role flag
    default_for_new_users = Column(Boolean, default=False, nullable=False, server_default='false')
    active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user_role_main = relationship("UserRoleMain", back_populates="basic")

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

    # Button permissions stored as JSONB (same shape as menu_permissions)
    # Format: [{"id": "button-uuid", "access": ["read", "write"]}, ...]
    button_permissions = Column(postgresql.JSONB, nullable=False, default=[], server_default='[]')

    # Highest button access level (read / write / disable)
    button_access = Column(String(50), nullable=True, default='disable', server_default='disable')

    # Form permissions stored as JSONB (same shape as menu_permissions)
    # Format: [{"id": "form-uuid", "application_id": "...", "modules_id": "...", "access": ["read","write"]}, ...]
    form_permissions = Column(postgresql.JSONB, nullable=False, default=[], server_default='[]')

    # Highest form access level (read / write / disable)
    form_access = Column(String(50), nullable=True, default='disable', server_default='disable')

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user_role_main = relationship("UserRoleMain", back_populates="permissions")
    userrole_basic = relationship("UserRoleBasic", backref="permissions")

    def __repr__(self):
        return f"<UserRolePermission(id={self.id}, userrole_basic_id={self.userrole_basic_id}, menu_access={self.menu_access})>"

