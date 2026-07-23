from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid


class TenantModule(Base):
    """
    Junction table — many-to-many between tenants and modules.
    One module (e.g. Scheduling) can be assigned to many tenants.
    One tenant can have many modules.
    """
    __tablename__ = "tenant_modules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False, index=True)
    module_id = Column(UUID(as_uuid=True), ForeignKey("modules.id", ondelete="CASCADE"), nullable=False, index=True)

    is_active = Column(Boolean, default=True, nullable=False)
    notes = Column(Text, nullable=True)

    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    assigned_by = Column(UUID(as_uuid=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by = Column(UUID(as_uuid=True), nullable=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="tenant_modules")
    module = relationship("Module", back_populates="tenant_modules")

    __table_args__ = (
        UniqueConstraint("tenant_id", "module_id", name="uq_tenant_module"),
    )

    def __repr__(self):
        return f"<TenantModule(tenant_id={self.tenant_id}, module_id={self.module_id}, is_active={self.is_active})>"
