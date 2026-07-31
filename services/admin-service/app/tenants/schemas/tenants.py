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
    onboarding_status: Optional[str] = None
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
    primary_domain: Optional[str] = None
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

    # NOTE: tenant_db_name (derived from tenant_code), table_permission,
    # allowed_origins and is_active are intentionally NOT part of the schema —
    # they are operational/backend-managed and never accepted or returned here.

class TenantCreate(TenantBase):
    # Tenant creation is authorized by the caller's JWT (must be a master-DB
    # user, tenant_id NULL). No credentials are carried in the request body.
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
    onboarding_status: Optional[str] = None
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
    primary_domain: Optional[str] = None
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
