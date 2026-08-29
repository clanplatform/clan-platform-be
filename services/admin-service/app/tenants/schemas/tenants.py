from pydantic import BaseModel, Field, AnyHttpUrl
from typing import Optional, List
from datetime import datetime
from uuid import UUID

class TenantBase(BaseModel):
    tenant_name: str
    tenant_code: Optional[str] = None
    contact_email: str
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    initial_status: Optional[str] = Field(
        "Active",
        description="Tenant lifecycle status. One of: "
                    "Active (fully active), "
                    "Trial (active for 90 days, then automatically moves to Deactivate), "
                    "Pending setup (awaiting manual verification), "
                    "Deactivate (soft-deleted; purged permanently after 90 days).",
    )
    employees_count: Optional[int] = None
    description: Optional[str] = None

    # Company identity
    display_name: Optional[str] = None
    registration_number: Optional[str] = None
    tax_id: Optional[str] = None
    founded_year: Optional[int] = None
    website: Optional[str] = None
    company_logo: Optional[str] = None
    annual_revenue: Optional[str] = None
    # Headquarters address
    postal_code: Optional[str] = None
    # Primary contact
    contact_name: Optional[str] = None
    contact_title: Optional[str] = None
    # Business domain & model
    # primary_domain_id -> domains.id (the tenant's industry vertical). The
    # vertical's domains.branch_compliance_key drives which branch compliance
    # section its branches seed. primary_domain_name / branch_compliance_key are
    # read-only (TenantResponse) — do NOT add them here (create_tenant does
    # Tenant(**model_dump()) and a non-column key would blow up).
    primary_domain_id: Optional[UUID] = None
    business_model: Optional[str] = None
    organization_type: Optional[str] = None
    # Localization & business defaults
    default_language: Optional[str] = None
    time_zone: Optional[str] = None
    default_currency: Optional[str] = None
    date_format: Optional[str] = None
    fiscal_year_start: Optional[str] = None
    week_starts_on: Optional[str] = None
    # Account status
    internal_notes: Optional[str] = None
    # Account owner (denormalized; owner password is never stored/returned here)
    owner_name: Optional[str] = None
    owner_email: Optional[str] = None

    # NOTE: tenant_db_name (derived from tenant_code), table_permission and
    # allowed_origins are intentionally NOT part of the schema — they are
    # operational/backend-managed and never accepted or returned here.
    # is_active is also backend-managed (derived from initial_status, see
    # create_tenant()/create_onboarding()) — it's never accepted on
    # create/update, but is surfaced read-only on TenantResponse below.

class TenantCreate(TenantBase):
    # Tenant creation is authorized by the caller's JWT (must be a master-DB
    # user, tenant_id NULL). The owner's password is never accepted here —
    # it's always randomly generated server-side (see create_tenant()) and
    # returned once via TenantCreateResponse.temp_password.
    pass

class TenantUpdate(BaseModel):
    tenant_name: Optional[str] = None
    tenant_code: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    initial_status: Optional[str] = Field(
        None,
        description="Active, Trial, Pending setup, or Deactivate — see TenantBase.initial_status.",
    )
    employees_count: Optional[int] = None
    description: Optional[str] = None
    display_name: Optional[str] = None
    registration_number: Optional[str] = None
    tax_id: Optional[str] = None
    founded_year: Optional[int] = None
    website: Optional[str] = None
    company_logo: Optional[str] = None
    annual_revenue: Optional[str] = None
    postal_code: Optional[str] = None
    contact_name: Optional[str] = None
    contact_title: Optional[str] = None
    primary_domain_id: Optional[UUID] = None
    business_model: Optional[str] = None
    organization_type: Optional[str] = None
    default_language: Optional[str] = None
    time_zone: Optional[str] = None
    default_currency: Optional[str] = None
    date_format: Optional[str] = None
    fiscal_year_start: Optional[str] = None
    week_starts_on: Optional[str] = None
    internal_notes: Optional[str] = None
    owner_name: Optional[str] = None
    owner_email: Optional[str] = None

class TenantResponse(TenantBase):
    tenant_id: UUID
    is_active: Optional[bool] = Field(
        None,
        description="tenants.is_active — backend-derived from initial_status "
                    "('Active' => true, anything else => false); read-only, "
                    "never accepted on create/update.",
    )
    # Read-only, resolved from primary_domain_id -> domains (see Tenant model props)
    primary_domain_name: Optional[str] = Field(None, description="domains.name of the tenant's vertical")
    branch_compliance_key: Optional[str] = Field(
        None,
        description="domains.branch_compliance_key of the tenant's vertical — the "
                    "branch-form compliance section its branches seed (e.g. "
                    "'entities_healthcare'), or null if the vertical has none.",
    )
    gateway_tenant_ref: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    created_by: Optional[UUID] = None

    class Config:
        from_attributes = True

class TenantListResponse(BaseModel):
    tenants: List[TenantResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

class TenantCreateResponse(TenantResponse):
    temp_password: str = Field(
        ...,
        description="Temporary password for the initial admin user. Must be changed on first login.",
    )

class TenantConfigurationStatus(BaseModel):
    tenant_id: UUID
    has_entities: bool
    entities_count: int
    has_organizational_structure: bool
    departments_count: int
    divisions_count: int
    has_job_codes: bool
    job_codes_count: int
    has_users: bool
    users_count: int
    setup_completion_percentage: int
    recommended_next_steps: List[str]
