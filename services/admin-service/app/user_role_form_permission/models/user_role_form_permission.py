from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Sequence
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.infrastructure.database.base import Base

_sino_seq = Sequence('role_form_permission_sino_seq')


class RoleFormPermission(Base):
    """
    Role Form Permission Model
    Stores form permissions for user roles separately from menu permissions
    """
    __tablename__ = "user_role_form_permission"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)

    # Serial number — sequence is declared here so create_all() emits CREATE SEQUENCE first
    sino = Column(
        Integer,
        _sino_seq,
        server_default=_sino_seq.next_value(),
        nullable=False,
        unique=True,
        index=True,
    )
    
    # Foreign keys to user role tables
    user_role_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_role.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to user_role (UserRoleMain) table"
    )
    
    userrole_basic_id = Column(
        UUID(as_uuid=True),
        ForeignKey("userrole_basic.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to userrole_basic table"
    )
    
    userrole_permission_id = Column(
        UUID(as_uuid=True),
        ForeignKey("userrole_permission.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to userrole_permission table (required - to get menu selections)"
    )
    
    # Form permissions stored as JSONB array
    # Structure: [{"id": "form-uuid", "application_id": "app-uuid", "modules_id": "module-uuid", "access": ["read", "write"]}]
    form_permissions = Column(
        JSONB,
        nullable=False,
        default=[],
        comment="Array of form permissions with individual access levels"
    )
    
    # Highest form access level (calculated from form_permissions array)
    # Values: 'read', 'write', 'disable'
    form_access = Column(
        String(20),
        nullable=True,
        default="disable",
        comment="Highest form access level: read, write, or disable"
    )
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user_role = relationship("UserRoleMain", back_populates="form_permissions")
    userrole_basic = relationship("UserRoleBasic", back_populates="form_permissions")
    userrole_permission = relationship("UserRolePermission", back_populates="role_form_permissions")

    def __repr__(self):
        return f"<RoleFormPermission(id={self.id}, user_role_id={self.user_role_id}, form_access={self.form_access})>"

    class Config:
        orm_mode = True
