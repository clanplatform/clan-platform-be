from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid


class Subscription(Base):
    """
    A tenant's subscription: plan, application/module grants and add-on limits —
    the onboarding "Subscription plan" step.
    """
    __tablename__ = "subscription"

    subscription_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    # Derived from the JWT (never accepted/returned in the CRUD schema):
    #   NULL     -> master-DB user (token has no tenant_id)
    #   a tenant -> tenant-DB user (token's tenant_id)
    # Nullable so master-DB users can create rows in the master DB.
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.tenant_id"), nullable=True, index=True)

    # Subscription plan
    plan = Column(String(50), nullable=True)            # Standard | Professional | Enterprise
    billing_cycle = Column(String(20), nullable=True)   # Annual | Monthly | Quarterly
    licensed_user_seats = Column(Integer, nullable=True)
    start_as_trial = Column(Boolean, nullable=False, server_default='false', default=False)

    # Grants — ids of platform applications / modules to grant (loaded live in the UI)
    applications_to_grant = Column(ARRAY(UUID(as_uuid=True)), nullable=True)
    modules_to_grant = Column(ARRAY(UUID(as_uuid=True)), nullable=True)

    # Add-ons & limits
    extra_storage = Column(String(50), nullable=True)   # None | 50GB | 100GB | ...
    support_tier = Column(String(50), nullable=True)
    api_access = Column(Boolean, nullable=False, server_default='false', default=False)
    sandbox_environment = Column(Boolean, nullable=False, server_default='false', default=False)
    white_label_branding = Column(Boolean, nullable=False, server_default='false', default=False)

    is_active = Column(Boolean, nullable=False, server_default='true', default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(UUID(as_uuid=True), nullable=True)

    def __repr__(self):
        return f"<Subscription(id={self.subscription_id}, plan={self.plan}, tenant_id={self.tenant_id})>"
