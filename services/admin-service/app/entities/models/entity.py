from sqlalchemy import Column, Integer, String, DateTime, Date, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid

class Entity(Base):
    __tablename__ = "entities"

    entity_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    # Derived from the JWT (never accepted/returned in the CRUD schema):
    #   NULL       -> master-DB user (token has no tenant_id)
    #   a tenant   -> tenant-DB user (token's tenant_id)
    # Nullable so master-DB users can create rows in the master DB.
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.tenant_id"), nullable=True)
    entity_name = Column(String(100), nullable=False)
    entity_code = Column(String(20), nullable=False)
    company_size = Column(String(50), nullable=True)
    contact = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True)
    address_1 = Column(String(200), nullable=True)
    address_2 = Column(String(200), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    time_zone = Column(String(50), nullable=True)
    time_zone_offset = Column(String(10), nullable=True)
    date_format = Column(String(20), nullable=True)
    time_format = Column(String(20), nullable=True)
    date_time_format = Column(String(40), nullable=True)
    # Localization & business defaults — mirror tenants' own columns of the
    # same name; auto-copied from the tenant when it has
    # use_default_localization=true (see create_entity()).
    default_language = Column(String(50), nullable=True)
    default_currency = Column(String(10), nullable=True)
    fiscal_year_start = Column(String(20), nullable=True)
    week_starts_on = Column(String(20), nullable=True)

    # Branch profile (Add-branch form)
    location_type = Column(String(50), nullable=True)
    is_headquarters = Column(Boolean, nullable=False, server_default='false', default=False)
    phone = Column(String(20), nullable=True)
    tax_registration = Column(String(100), nullable=True)
    postal_code = Column(String(20), nullable=True)

    # Operating schedule (defaults)
    working_days = Column(String(100), nullable=True)          # e.g. "Mon,Tue,Wed,Thu,Fri"
    business_hours_start = Column(String(10), nullable=True)    # e.g. "09:00"
    business_hours_end = Column(String(10), nullable=True)      # e.g. "18:00"
    observes_dst = Column(Boolean, nullable=False, server_default='false', default=False)

    # Compliance & documents (stored file references / URLs)
    business_registration_doc = Column(String(500), nullable=True)
    tax_certificate_doc = Column(String(500), nullable=True)
    incorporation_certificate_doc = Column(String(500), nullable=True)
    data_processing_agreement_doc = Column(String(500), nullable=True)
    insurance_certificate_doc = Column(String(500), nullable=True)
    other_documents_doc = Column(String(500), nullable=True)

    active = Column(Boolean, nullable=False, server_default='true', default=True)
    deleted = Column(Boolean, nullable=False, server_default='false', default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    departments = relationship("Department", back_populates="entity")
    divisions = relationship("Division", back_populates="entity")

    def __repr__(self):
        return f"<Entity(id={self.entity_id}, name={self.entity_name}, tenant_id={self.tenant_id})>"