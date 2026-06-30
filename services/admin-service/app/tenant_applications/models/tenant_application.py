from sqlalchemy import Column, Boolean, DateTime, Text, UniqueConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid


class TenantApplication(Base):
    """
    Junction table — many-to-many between tenants and applications.

    Licensing tiers:
      - Tier 1: A tenant buys individual modules    → use tenant_modules
      - Tier 2: A tenant buys an entire application → use tenant_applications
      - Tier 3: A tenant buys the full platform     → set subscription_plan='platform' on tenants

    When a TenantApplication row exists (and is_active=True), the tenant has
    access to ALL modules under that application without needing individual
    tenant_modules rows.
    """

    __tablename__ = "tenant_applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    application_id = Column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    is_active = Column(Boolean, default=True, nullable=False)
    notes = Column(Text, nullable=True)

    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    assigned_by = Column(UUID(as_uuid=True), nullable=True)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by = Column(UUID(as_uuid=True), nullable=True)

    tenant = relationship("Tenant", backref="tenant_applications")
    application = relationship("Application", backref="tenant_applications")

    __table_args__ = (
        UniqueConstraint("tenant_id", "application_id", name="uq_tenant_application"),
    )
