from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Boolean, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid



class Department(Base):
    __tablename__ = "departments"
    
    department_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.tenant_id"), nullable=False)
    entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False)
    parent_department_id = Column(UUID(as_uuid=True), ForeignKey("departments.department_id"), nullable=True)
    department_name = Column(String(100), nullable=False)
    department_code = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    department_type = Column(String(50), nullable=True)
    cost_center = Column(String(50), nullable=True)
    budget_info = Column(JSON, default=dict)
    # manager_id removed - column doesn't exist in database
    location = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=False)
    email = Column(String(255), nullable=False)
    annual_budget = Column(Numeric(15, 2), nullable=False)
    reporting_structure = Column(String(100), nullable=False)
    department_metadata = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by = Column(UUID(as_uuid=True), nullable=True)
    updated_by = Column(UUID(as_uuid=True), nullable=True)
    
    # Relationships
    tenant = relationship("Tenant")
    entity = relationship("Entity", back_populates="departments")
    divisions = relationship("Division", back_populates="department")
    parent_department = relationship("Department", remote_side=[department_id], foreign_keys=[parent_department_id])
    child_departments = relationship("Department", foreign_keys=[parent_department_id], overlaps="parent_department")
    
    def __repr__(self):
        return f"<Department(id={self.department_id}, name={self.department_name}, entity_id={self.entity_id})>"
