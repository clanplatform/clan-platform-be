"""
Logistics & Supply chain model for a branch (entity).

One row per branch (`entities` row) — the branch form's "Logistics & supply
chain" section. It holds the fleet / warehouse / transport fields shown on that
section of the form.

Lives in every tenant DB (created fresh via Base.metadata.create_all() at
provisioning time, so new tenants get it automatically) and in the master DB.
Already-provisioned tenant DBs get it via
scripts/migrations/create_logistics_supply_chain_table.sql.

The nested `logistics_supply_chain` object carried inside a branch (see
EntityBase / OnboardingBranch) upserts onto the single unique `entity_id` row;
`id` / `entity_id` / `tenant_id` / `active` / `deleted` are backend-managed and
never part of the request/response schema.
"""
from sqlalchemy import (
    Column, String, Integer, Text, DateTime, Boolean, ForeignKey, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid


class LogisticsSupplyChain(Base):
    __tablename__ = "logistics_supply_chain"
    __table_args__ = (
        # One logistics/supply-chain row per branch.
        UniqueConstraint("entity_id", name="uq_logistics_supply_chain_entity"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    entity_id = Column(
        UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=False, index=True
    )
    # Derived from the JWT (never accepted/returned in the schema):
    #   NULL     -> master-DB user (token has no tenant_id)
    #   a tenant -> tenant-DB user (token's tenant_id)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.tenant_id"), nullable=True, index=True)

    # Logistics & supply chain
    fleet_size = Column(String(100), nullable=True)        # "Fleet size" (e.g. 120 vehicles)
    warehouses_dcs = Column(Integer, nullable=True)        # "Warehouses / DCs"
    transport_modes = Column(ARRAY(Text), nullable=True)   # "Transport modes" (multi-select)
    wms_tms_system = Column(String(150), nullable=True)    # "WMS / TMS system" (e.g. Manhattan, Blue Yonder)

    active = Column(Boolean, nullable=False, server_default="true", default=True)
    deleted = Column(Boolean, nullable=False, server_default="false", default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships (one-directional — Entity.logistics_supply_chain is viewonly)
    entity = relationship("Entity", foreign_keys=[entity_id], overlaps="logistics_supply_chain")
    tenant = relationship("Tenant", foreign_keys=[tenant_id])

    def __repr__(self):
        return f"<LogisticsSupplyChain(id={self.id}, entity_id={self.entity_id})>"
