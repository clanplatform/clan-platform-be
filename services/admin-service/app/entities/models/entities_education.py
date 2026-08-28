"""
Education institution model for a branch (entity).

One row per branch (`entities` row) — the branch form's "Education institution"
section. It holds the institution-type / enrolment / campus / accreditation
fields shown on that section of the form.

Lives in every tenant DB (created fresh via Base.metadata.create_all() at
provisioning time, so new tenants get it automatically) and in the master DB.
Already-provisioned tenant DBs get it via
scripts/migrations/create_entities_education_table.sql.

The nested `entities_education` object carried inside a branch (see EntityBase /
OnboardingBranch) upserts onto the single unique `entity_id` row; `id` /
`entity_id` / `tenant_id` / `active` / `deleted` are backend-managed and never
part of the request/response schema.
"""
from sqlalchemy import (
    Column, String, Integer, DateTime, Boolean, ForeignKey, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid


class EntitiesEducation(Base):
    __tablename__ = "entities_education"
    __table_args__ = (
        # One education-institution row per branch.
        UniqueConstraint("entity_id", name="uq_entities_education_entity"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    entity_id = Column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    # Derived from the JWT (never accepted/returned in the schema):
    #   NULL     -> master-DB user (token has no tenant_id)
    #   a tenant -> tenant-DB user (token's tenant_id)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.tenant_id"), nullable=True, index=True)

    # Education institution
    institution_type = Column(String(100), nullable=True)   # "Institution type" (select)
    students_enrolled = Column(Integer, nullable=True)       # "Students enrolled"
    campuses = Column(Integer, nullable=True)                # "Campuses"
    accreditation_body = Column(String(100), nullable=True)  # "Accreditation body" (e.g. AACSB, regional)

    active = Column(Boolean, nullable=False, server_default="true", default=True)
    deleted = Column(Boolean, nullable=False, server_default="false", default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships (one-directional — Entity.entities_education is viewonly)
    entity = relationship("Entity", foreign_keys=[entity_id], overlaps="entities_education")
    tenant = relationship("Tenant", foreign_keys=[tenant_id])

    def __repr__(self):
        return f"<EntitiesEducation(id={self.id}, entity_id={self.entity_id})>"
