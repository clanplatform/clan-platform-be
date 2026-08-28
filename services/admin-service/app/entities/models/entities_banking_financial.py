"""
Banking & Financial services compliance model for a branch (entity).

One row per branch (`entities` row) — the branch form's "Financial services &
regulation" section. It holds the uploaded compliance-document references plus
the regulator / licensing / AML fields shown on that section of the form.

Lives in every tenant DB (created fresh via Base.metadata.create_all() at
provisioning time, so new tenants get it automatically) and in the master DB.
Already-provisioned tenant DBs get it via
scripts/migrations/create_entities_banking_financial_table.sql.

The nested `entities_banking_financial` object carried inside a branch (see
EntityBase / OnboardingBranch) upserts onto the single unique `entity_id` row;
`id` / `entity_id` / `tenant_id` / `active` / `deleted` are backend-managed and
never part of the request/response schema.
"""
from sqlalchemy import (
    Column, String, DateTime, Boolean, ForeignKey, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid


class EntitiesBankingFinancial(Base):
    __tablename__ = "entities_banking_financial"
    __table_args__ = (
        # One banking/financial-compliance row per branch.
        UniqueConstraint("entity_id", name="uq_entities_banking_financial_entity"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    entity_id = Column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    # Derived from the JWT (never accepted/returned in the schema):
    #   NULL     -> master-DB user (token has no tenant_id)
    #   a tenant -> tenant-DB user (token's tenant_id)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.tenant_id"), nullable=True, index=True)

    # Financial services compliance documents (stored file references / URLs)
    regulatory_license_doc = Column(String(500), nullable=True)     # "Regulatory license"
    aml_kyc_policy_doc = Column(String(500), nullable=True)         # "AML / KYC policy"
    pci_dss_attestation_doc = Column(String(500), nullable=True)    # "PCI-DSS attestation of compliance"

    # Financial services & regulation
    primary_regulator = Column(String(100), nullable=True)         # "Primary regulator" (e.g. SEC, FCA, RBI)
    license_type = Column(String(100), nullable=True)              # "License type" (select)
    license_number = Column(String(100), nullable=True)            # "License number"
    aml_compliance_officer = Column(String(200), nullable=True)    # "AML / compliance officer" (full name)
    kyc_level = Column(String(50), nullable=True)                  # "KYC level" (select)
    pci_dss_in_scope = Column(Boolean, nullable=False, server_default="false", default=False)

    active = Column(Boolean, nullable=False, server_default="true", default=True)
    deleted = Column(Boolean, nullable=False, server_default="false", default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships (one-directional — Entity.entities_banking_financial is viewonly)
    entity = relationship("Entity", foreign_keys=[entity_id], overlaps="entities_banking_financial")
    tenant = relationship("Tenant", foreign_keys=[tenant_id])

    def __repr__(self):
        return f"<EntitiesBankingFinancial(id={self.id}, entity_id={self.entity_id})>"
