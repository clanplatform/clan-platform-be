from sqlalchemy import Column, Integer, String, DateTime, Text, Date, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid

class Entity(Base):
    __tablename__ = "entities"

    entity_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.tenant_id"), nullable=False)
    entity_name = Column(String(100), nullable=False)
    entity_code = Column(String(20), nullable=False)
    company_size = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    contact = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True)
    address_1 = Column(String(200), nullable=True)
    address_2 = Column(String(200), nullable=True)
    city_code = Column(String(10), nullable=True)
    state_code = Column(String(10), nullable=True)
    country_code = Column(String(10), nullable=True)
    time_zone = Column(String(50), nullable=True)
    time_zone_offset = Column(String(10), nullable=True)
    date_format = Column(String(20), nullable=True)
    time_format = Column(String(20), nullable=True)
    date_time_format = Column(String(40), nullable=True)
    active = Column(Boolean, nullable=False, server_default='true', default=True)
    deleted = Column(Boolean, nullable=False, server_default='false', default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="entities")
    departments = relationship("Department", back_populates="entity")
    divisions = relationship("Division", back_populates="entity")

    def __repr__(self):
        return f"<Entity(id={self.entity_id}, name={self.entity_name}, tenant_id={self.tenant_id})>"