from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid

class Tenant(Base):
    __tablename__ = "tenants"

    tenant_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    tenant_name = Column(String(255), nullable=False)
    tenant_code = Column(String(100), nullable=True)
    contact_email = Column(String(255), nullable=False)
    contact_phone = Column(String(50), nullable=True)
    # Headquarters address
    address = Column(String(500), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    postal_code = Column(String(20), nullable=True)

    # Primary contact (email/phone are above)
    contact_name = Column(String(255), nullable=True)
    contact_title = Column(String(100), nullable=True)

    # Company identity
    display_name = Column(String(255), nullable=True)           # Display / brand name
    industry = Column(String(100), nullable=True)               # Industry / sub-sector
    registration_number = Column(String(100), nullable=True)
    tax_id = Column(String(100), nullable=True)                 # Tax / VAT / GST ID
    founded_year = Column(Integer, nullable=True)
    website = Column(String(255), nullable=True)
    deployed_url = Column(String(500), nullable=True)           # URL of the tenant's deployed application instance
    company_logo = Column(String(500), nullable=True)           # Logo URL / file reference
    company_size = Column(String(50), nullable=True)
    employees_count = Column(Integer, nullable=True)
    annual_revenue = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)                   # Company description

    # Business domain & model
    primary_domain = Column(String(100), nullable=True)
    business_model = Column(String(100), nullable=True)
    organization_type = Column(String(100), nullable=True)

    # Localization & business defaults
    default_language = Column(String(50), nullable=True)
    time_zone = Column(String(50), nullable=True)
    default_currency = Column(String(10), nullable=True)
    date_format = Column(String(20), nullable=True)
    fiscal_year_start = Column(String(20), nullable=True)
    week_starts_on = Column(String(20), nullable=True)
    # When true, new branches (entities) inherit the 6 fields above instead of
    # setting their own — see create_entity()'s use_default_localization check.
    use_default_localization = Column(Boolean, nullable=False, server_default='false', default=False)

    # Status — "Initial status" (Active / Trial / Pending setup) selected on
    # the account-status step. is_active (below) is derived from it at
    # creation ('Active' => true, else => false) — backend-only, not on
    # any schema.
    initial_status = Column(String(50), nullable=True, server_default='Active')
    internal_notes = Column(Text, nullable=True)                # platform-admin only

    # Account owner (denormalized from the owner user for display). The
    # actual login credential is hashed on usersetup_basic; owner_password_hash
    # here is a write-only convenience copy (bcrypt-hashed, never the raw
    # value) — never returned by the API (see TenantBase/TenantResponse).
    owner_name = Column(String(200), nullable=True)
    owner_email = Column(String(255), nullable=True)
    owner_password_hash = Column(String(255), nullable=True)

    gateway_tenant_ref = Column(UUID(as_uuid=True), unique=True, nullable=True, default=None, index=True)
    table_permission = Column(ARRAY(Text), nullable=True, default=list)
    allowed_origins = Column(ARRAY(Text), nullable=True, default=list)
    is_active = Column(Boolean, nullable=True, server_default='true')
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(UUID(as_uuid=True), nullable=True)

    # Relationships
    tenant_modules = relationship("TenantModule", back_populates="tenant", cascade="all, delete-orphan")

    @property
    def tenant_db_name(self):
        """Derived from tenant_code (not stored): clan_platform_<slug(tenant_code)>.
        Returns None when tenant_code is missing."""
        if not self.tenant_code:
            return None
        from app.infrastructure.database.tenant_db_manager import TenantDatabaseManager
        return TenantDatabaseManager.make_db_name(self.tenant_code)

    def __repr__(self):
        return f"<Tenant(tenant_name='{self.tenant_name}', is_active='{self.is_active}')>"
