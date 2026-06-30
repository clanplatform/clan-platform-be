from sqlalchemy import Column, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid

class Division(Base):
    __tablename__ = "divisions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.tenant_id"), nullable=False)
    entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False)
    division_name = Column(String(100), nullable=False)
    division_code = Column(String(20), nullable=False)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.department_id"), nullable=True)
    description = Column(Text, nullable=True)
    parent_division_id = Column(UUID(as_uuid=True), ForeignKey("divisions.id"), nullable=True)
    hierarchy_level = Column(String(10), default="1")
    division_metadata = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    tenant = relationship("Tenant")
    entity = relationship("Entity", back_populates="divisions")
    department = relationship("Department", back_populates="divisions")
    parent_division = relationship("Division", remote_side=[id], back_populates="child_divisions")
    child_divisions = relationship("Division", back_populates="parent_division", overlaps="parent_division")
    
    def __repr__(self):
        return f"<Division(id={self.id}, name={self.division_name}, code={self.division_code})>"
