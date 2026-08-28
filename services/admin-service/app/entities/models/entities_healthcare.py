"""
Healthcare compliance model for a branch (entity).

One row per branch (`entities` row) — the branch form's "Healthcare facility &
compliance" section. It holds the uploaded compliance-document references plus
the facility / HIPAA fields shown on that section of the form.

Lives in every tenant DB (created fresh via Base.metadata.create_all() at
provisioning time, so new tenants get it automatically) and in the master DB.
Already-provisioned tenant DBs get it via
scripts/migrations/create_entities_healthcare_table.sql.

The nested `entities_healthcare` object carried inside a branch (see
EntityBase / OnboardingBranch) upserts onto the single unique `entity_id` row;
`id` / `entity_id` / `tenant_id` / `active` / `deleted` are backend-managed and
never part of the request/response schema.
"""
from sqlalchemy import (
    Column, String, Integer, Date, DateTime, Boolean, ForeignKey, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid


class EntitiesHealthcare(Base):
    __tablename__ = "entities_healthcare"
    __table_args__ = (
        # One healthcare-compliance row per branch.
        UniqueConstraint("entity_id", name="uq_entities_healthcare_entity"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    entity_id = Column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    # Derived from the JWT (never accepted/returned in the schema):
    #   NULL     -> master-DB user (token has no tenant_id)
    #   a tenant -> tenant-DB user (token's tenant_id)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.tenant_id"), nullable=True, index=True)

    # Healthcare compliance documents (stored file references / URLs)
    facility_license_doc = Column(String(500), nullable=True)               # "Facility license"
    accreditation_certificate_doc = Column(String(500), nullable=True)      # "Accreditation certificate"
    dea_registration_doc = Column(String(500), nullable=True)               # "DEA / controlled-substance registration"
    hipaa_compliance_attestation_doc = Column(String(500), nullable=True)   # "HIPAA compliance attestation"

    # Healthcare facility & compliance
    facility_type = Column(String(100), nullable=True)                      # "Facility type" (select)
    npi_number = Column(String(50), nullable=True)                          # "NPI number"
    facility_license_no = Column(String(100), nullable=True)               # "Facility license no."
    license_expiry = Column(Date, nullable=True)                            # "License expiry"
    accreditation = Column(String(100), nullable=True)                     # "Accreditation" (accreditation body, select)
    bed_capacity = Column(Integer, nullable=True)                           # "Bed capacity"
    licensed_practitioners = Column(Integer, nullable=True)                 # "Licensed practitioners"
    ehr_emr_system = Column(String(150), nullable=True)                    # "EHR / EMR system"
    hipaa_privacy_officer = Column(String(200), nullable=True)            # "HIPAA privacy officer" (full name)
    officer_email = Column(String(255), nullable=True)                     # "Officer email"
    telehealth_enabled = Column(Boolean, nullable=False, server_default="false", default=False)
    handles_phi = Column(Boolean, nullable=False, server_default="false", default=False)

    active = Column(Boolean, nullable=False, server_default="true", default=True)
    deleted = Column(Boolean, nullable=False, server_default="false", default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships (one-directional — Entity.entities_healthcare is viewonly)
    entity = relationship("Entity", foreign_keys=[entity_id], overlaps="entities_healthcare")
    tenant = relationship("Tenant", foreign_keys=[tenant_id])

    def __repr__(self):
        return f"<EntitiesHealthcare(id={self.id}, entity_id={self.entity_id})>"
