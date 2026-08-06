from sqlalchemy import Column, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid


class UserGroup(Base):
    __tablename__ = "users_group"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Derived from the JWT (never accepted/returned in the CRUD schema):
    #   NULL     -> master-DB user (token has no tenant_id)
    #   a tenant -> tenant-DB user (token's tenant_id)
    # Nullable so master-DB users can create rows in the master DB.
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.tenant_id"), nullable=True)
    group_name = Column(String(100), nullable=False)
    group_code = Column(String(50), nullable=True)
    # Default role assigned to users placed in this group (user_role.id, the
    # parent role PK — same convention as usersetup_basic.role_id).
    default_role_id = Column(UUID(as_uuid=True), ForeignKey("user_role.id"), nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant")
    default_role = relationship("UserRoleMain", foreign_keys=[default_role_id])

    def __repr__(self):
        return f"<UserGroup(id={self.id}, name={self.group_name}, code={self.group_code})>"
