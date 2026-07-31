from sqlalchemy import Column, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid

class Division(Base):
    __tablename__ = "divisions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Derived from the JWT (never accepted/returned in the CRUD schema):
    #   NULL     -> master-DB user (token has no tenant_id)
    #   a tenant -> tenant-DB user (token's tenant_id)
    # Nullable so master-DB users can create rows in the master DB.
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.tenant_id"), nullable=True)
    entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False)
    division_name = Column(String(100), nullable=False)
    division_code = Column(String(20), nullable=False)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.department_id"), nullable=True)
    description = Column(Text, nullable=True)
    division_head = Column(String(100), nullable=True)   # Head / lead (name)
    hierarchy_level = Column(String(10), default="1")
    is_active = Column(Boolean, default=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    tenant = relationship("Tenant")
    entity = relationship("Entity", back_populates="divisions")
    department = relationship("Department", back_populates="divisions")

    def __repr__(self):
        return f"<Division(id={self.id}, name={self.division_name}, code={self.division_code})>"
