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
    subscription_plan: Optional[str] = None
    onboarding_status: Optional[str] = None
    employees_count: Optional[int] = None
    location: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    tenant_db_name: Optional[str] = None
    table_permission: Optional[List[str]] = Field(
        default=None,
        description="List of table names allocated in this tenant's dedicated database.",
        json_schema_extra={"example": ["users", "departments", "job_codes"]},
    )
    is_active: Optional[bool] = True
    allowed_origins: Optional[List[str]] = Field(
        default=None,
        description="List of allowed CORS origins for this tenant's frontend apps.",
        json_schema_extra={"example": ["https://app.customer.com", "https://portal.customer.org"]},
    )

class TenantCreate(TenantBase):
    # Tenant DBs may only be provisioned by a master-DB user (usersetup_basic
    # with tenant_id NULL). The creator re-authenticates with email + password;
    # tenant users are rejected. These fields are consumed by the route and
    # never stored on the tenant row.
    created_by_email: str = Field(
        ...,
        description="Email of the master-DB user (usersetup_basic) authorizing this tenant creation.",
    )
    created_by_password: str = Field(
        ...,
        description="Password of the master-DB user authorizing this tenant creation.",
    )

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
    subscription_plan: Optional[str] = None
    onboarding_status: Optional[str] = None
    employees_count: Optional[int] = None
    location: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    tenant_db_name: Optional[str] = None
    table_permission: Optional[List[str]] = None
    is_active: Optional[bool] = None
    allowed_origins: Optional[List[str]] = None

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
