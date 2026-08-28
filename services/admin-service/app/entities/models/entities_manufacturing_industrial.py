"""
Manufacturing & Industrial compliance model for a branch (entity).

One row per branch (`entities` row) — the branch form's "Manufacturing plant &
production" section. It holds the uploaded compliance-document references plus
the plant / production fields shown on that section of the form.

Lives in every tenant DB (created fresh via Base.metadata.create_all() at
provisioning time, so new tenants get it automatically) and in the master DB.
Already-provisioned tenant DBs get it via
scripts/migrations/create_entities_manufacturing_industrial_table.sql.

The nested `entities_manufacturing_industrial` object carried inside a branch
(see EntityBase / OnboardingBranch) upserts onto the single unique `entity_id`
row; `id` / `entity_id` / `tenant_id` / `active` / `deleted` are
backend-managed and never part of the request/response schema.
"""
from sqlalchemy import (
    Column, String, Integer, Text, DateTime, Boolean, ForeignKey, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid


class EntitiesManufacturingIndustrial(Base):
    __tablename__ = "entities_manufacturing_industrial"
    __table_args__ = (
        # One manufacturing-compliance row per branch.
        UniqueConstraint("entity_id", name="uq_entities_manufacturing_industrial_entity"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    entity_id = Column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    # Derived from the JWT (never accepted/returned in the schema):
    #   NULL     -> master-DB user (token has no tenant_id)
    #   a tenant -> tenant-DB user (token's tenant_id)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.tenant_id"), nullable=True, index=True)

    # Manufacturing compliance documents (stored file references / URLs)
    iso_certificates_doc = Column(String(500), nullable=True)          # "ISO certificates"
    safety_osha_compliance_doc = Column(String(500), nullable=True)    # "Safety / OSHA compliance"
    environmental_permit_doc = Column(String(500), nullable=True)      # "Environmental permit"

    # Manufacturing plant & production
    plant_type = Column(String(100), nullable=True)                    # "Plant type" (select)
    production_lines = Column(Integer, nullable=True)                  # "Production lines"
    shift_pattern = Column(String(100), nullable=True)                # "Shift pattern" (select)
    production_capacity = Column(String(100), nullable=True)          # "Production capacity" (e.g. 10k units/day)
    iso_certifications = Column(ARRAY(Text), nullable=True)           # "ISO certifications" (multi-select)
    erp_mes_system = Column(String(150), nullable=True)              # "ERP / MES system" (e.g. SAP S/4HANA)
    handles_hazardous_materials = Column(Boolean, nullable=False, server_default="false", default=False)
    unionized_workforce = Column(Boolean, nullable=False, server_default="false", default=False)

    active = Column(Boolean, nullable=False, server_default="true", default=True)
    deleted = Column(Boolean, nullable=False, server_default="false", default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships (one-directional — Entity.entities_manufacturing_industrial is viewonly)
    entity = relationship("Entity", foreign_keys=[entity_id], overlaps="entities_manufacturing_industrial")
    tenant = relationship("Tenant", foreign_keys=[tenant_id])

    def __repr__(self):
        return f"<EntitiesManufacturingIndustrial(id={self.id}, entity_id={self.entity_id})>"
