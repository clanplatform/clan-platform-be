from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid

class Tenant(Base):
    __tablename__ = "tenants"

    tenant_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    tenant_name = Column(String(255), nullable=False)
    tenant_code = Column(String(100), nullable=True)
    contact_email = Column(String(255), nullable=False)
    contact_phone = Column(String(50), nullable=True)
    address = Column(String(500), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    industry = Column(String(100), nullable=True)
    company_size = Column(String(50), nullable=True)
    subscription_plan = Column(String(100), nullable=True)
    onboarding_status = Column(String(50), nullable=True)
    employees_count = Column(Integer, nullable=True)
    location = Column(String(255), nullable=True)
    status = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    gateway_tenant_ref = Column(UUID(as_uuid=True), unique=True, nullable=True, default=None, index=True)
    tenant_db_name = Column(String(150), unique=True, nullable=True, index=True)
    table_permission = Column(ARRAY(Text), nullable=True, default=list)
    allowed_origins = Column(ARRAY(Text), nullable=True, default=list)
    is_active = Column(Boolean, nullable=True, server_default='true')
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(UUID(as_uuid=True), nullable=True)

    # Relationships
    entities = relationship("Entity", back_populates="tenant")
    tenant_modules = relationship("TenantModule", back_populates="tenant", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Tenant(tenant_name='{self.tenant_name}', is_active='{self.is_active}')>"
