"""
Retail & E-commerce compliance model for a branch (entity).

One row per branch (`entities` row) — the branch form's "Retail & store
operations" section. It holds the store / POS / e-commerce fields shown on that
section of the form.

Lives in every tenant DB (created fresh via Base.metadata.create_all() at
provisioning time, so new tenants get it automatically) and in the master DB.
Already-provisioned tenant DBs get it via
scripts/migrations/create_entities_retail_ecommerce_table.sql.

The nested `entities_retail_ecommerce` object carried inside a branch (see
EntityBase / OnboardingBranch) upserts onto the single unique `entity_id` row;
`id` / `entity_id` / `tenant_id` / `active` / `deleted` are backend-managed and
never part of the request/response schema.
"""
from sqlalchemy import (
    Column, String, Integer, DateTime, Boolean, ForeignKey, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid


class EntitiesRetailEcommerce(Base):
    __tablename__ = "entities_retail_ecommerce"
    __table_args__ = (
        # One retail-operations row per branch.
        UniqueConstraint("entity_id", name="uq_entities_retail_ecommerce_entity"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    entity_id = Column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    # Derived from the JWT (never accepted/returned in the schema):
    #   NULL     -> master-DB user (token has no tenant_id)
    #   a tenant -> tenant-DB user (token's tenant_id)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.tenant_id"), nullable=True, index=True)

    # Retail & store operations
    store_format = Column(String(100), nullable=True)      # "Store format" (select)
    number_of_stores = Column(Integer, nullable=True)      # "Number of stores"
    pos_terminals = Column(Integer, nullable=True)         # "POS terminals"
    pos_system = Column(String(150), nullable=True)        # "POS system" (e.g. Square, Shopify)
    ecommerce_enabled = Column(Boolean, nullable=False, server_default="false", default=False)
    loyalty_program = Column(Boolean, nullable=False, server_default="false", default=False)

    active = Column(Boolean, nullable=False, server_default="true", default=True)
    deleted = Column(Boolean, nullable=False, server_default="false", default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships (one-directional — Entity.entities_retail_ecommerce is viewonly)
    entity = relationship("Entity", foreign_keys=[entity_id], overlaps="entities_retail_ecommerce")
    tenant = relationship("Tenant", foreign_keys=[tenant_id])

    def __repr__(self):
        return f"<EntitiesRetailEcommerce(id={self.id}, entity_id={self.entity_id})>"
