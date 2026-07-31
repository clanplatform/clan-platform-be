"""
Onboarding Pydantic schemas.

The onboarding POST accepts the entire step-form as one graph and creates, in a
single sequence:

    tenant (client)  ->  branches (entities)  ->  departments  ->  divisions
                     ->  job codes  ->  roles  ->  users

Every created record carries a **client-generated UUID** (branches[].entity_id,
departments[].department_id, divisions[].id, roles[].id); each record is created
with that id, so children reference their parents by the real UUID:

    departments[i].entity_id         -> branches[].entity_id            (UUID)
    divisions[i].entity_id           -> branches[].entity_id            (UUID)
    divisions[i].department_id       -> departments[].department_id     (UUID, optional)
    job_codes[i].entity_id           -> branches[].entity_id            (UUID)
    job_codes[i].department_id       -> departments[].department_id     (UUID)
    job_codes[i].division_id         -> divisions[].id                  (UUID)
    roles[i].parent_role_id          -> roles[].id                      (UUID, optional)
    users[i].role_id                 -> roles[].id                      (UUID, optional)
    users[i].entity_id               -> branches[].entity_id            (UUID, optional; stored as default_entity)

All references are validated server-side by set membership; an unknown UUID
(or a duplicate client-supplied id) returns 422.
"""
from typing import List, Optional
from decimal import Decimal
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

from app.subscription.schemas.subscription import SubscriptionCreate
from app.security.schemas.security import SecurityCreate


# ============================================================================
# Step 1 — Client (tenant) + owner login
# ============================================================================

class OnboardingCompany(BaseModel):
    """Step 1: the client/company account (persisted to the tenants table)."""
    client_name: str = Field(..., min_length=1, max_length=255, description="Company / client name (tenants.tenant_name)")
    client_code: Optional[str] = Field(None, max_length=100, description="Short code; also seeds the tenant DB name (tenants.tenant_code)")
    industry: Optional[str] = Field(None, max_length=100)
    company_size: Optional[str] = Field(None, max_length=50)
    employees_count: Optional[int] = Field(None, ge=0)

    contact_email: str = Field(..., description="Primary contact email (tenants.contact_email)")
    contact_phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=500)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)

    # Company identity
    description: Optional[str] = Field(None, description="Company description")
    display_name: Optional[str] = Field(None, max_length=255, description="Display / brand name")
    registration_number: Optional[str] = Field(None, max_length=100)
    tax_id: Optional[str] = Field(None, max_length=100, description="Tax / VAT / GST ID")
    founded_year: Optional[int] = Field(None)
    website: Optional[str] = Field(None, max_length=255)
    annual_revenue: Optional[str] = Field(None, max_length=100)
    company_logo: Optional[str] = Field(None, max_length=500, description="Logo URL / file reference")

    # Primary contact (name + title)
    contact_name: Optional[str] = Field(None, max_length=255)
    contact_title: Optional[str] = Field(None, max_length=100)

    # Business domain & model
    primary_domain: Optional[str] = Field(None, max_length=100)
    business_model: Optional[str] = Field(None, max_length=100)
    organization_type: Optional[str] = Field(None, max_length=100)

    # Localization & business defaults
    default_language: Optional[str] = Field(None, max_length=50)
    time_zone: Optional[str] = Field(None, max_length=50)
    default_currency: Optional[str] = Field(None, max_length=10)
    date_format: Optional[str] = Field(None, max_length=20)
    fiscal_year_start: Optional[str] = Field(None, max_length=20)
    week_starts_on: Optional[str] = Field(None, max_length=20)

    # Account status
    status: Optional[str] = Field(
        "Active", max_length=50,
        description="Initial status -> tenants.is_active ('Active' => true, anything else => false)",
    )
    internal_notes: Optional[str] = Field(None, description="Notes visible to platform admins only")

    # Owner login — becomes the tenant's first admin user in the tenant DB.
    owner_name: Optional[str] = Field(None, max_length=200, description="Owner administrator full name")
    owner_email: str = Field(..., description="Account-admin (owner) login email; created as the first admin user")
    owner_password: str = Field(..., min_length=6, description="Account-admin (owner) login password")


# ============================================================================
# Step 2 — Branches (entities)
# ============================================================================

class OnboardingBranch(BaseModel):
    """Step 2: a branch / legal entity (persisted to the entities table)."""
    entity_id: UUID = Field(
        ...,
        description="Client-generated UUID (uuid4) for this branch/entity. The "
                    "entity is created with this id, and departments/divisions/"
                    "job_codes/users reference the branch by this same UUID.",
    )
    entity_name: str = Field(..., min_length=1, max_length=100, description="Branch / location name")
    entity_code: str = Field(..., min_length=1, max_length=20, description="Branch code")
    company_size: Optional[str] = Field(None, max_length=50)
    contact: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=255)
    address_1: Optional[str] = Field(None, max_length=200)
    address_2: Optional[str] = Field(None, max_length=200)
    city: Optional[str] = Field(None, max_length=100, description="City")
    state: Optional[str] = Field(None, max_length=100, description="State / province")
    country: Optional[str] = Field(None, max_length=100, description="Country")
    postal_code: Optional[str] = Field(None, max_length=20)
    time_zone: Optional[str] = Field(None, max_length=50, description="Site timezone (IANA, e.g. Asia/Kolkata)")
    location_type: Optional[str] = Field(None, max_length=50)
    is_headquarters: bool = Field(default=False, description="Headquarters flag")
    phone: Optional[str] = Field(None, max_length=20)
    tax_registration: Optional[str] = Field(None, max_length=100, description="Local tax / GST no.")
    # Operating schedule (defaults)
    working_days: Optional[str] = Field(None, max_length=100, description="Comma-separated day names, e.g. 'Mon,Tue,Wed'")
    business_hours_start: Optional[str] = Field(None, max_length=10, description="e.g. '09:00'")
    business_hours_end: Optional[str] = Field(None, max_length=10, description="e.g. '18:00'")
    observes_dst: bool = Field(default=False, description="Observes daylight saving")
    # Compliance & documents (uploaded file references / URLs)
    business_registration_doc: Optional[str] = Field(None, max_length=500)
    tax_certificate_doc: Optional[str] = Field(None, max_length=500)
    incorporation_certificate_doc: Optional[str] = Field(None, max_length=500)
    data_processing_agreement_doc: Optional[str] = Field(None, max_length=500)
    insurance_certificate_doc: Optional[str] = Field(None, max_length=500)
    other_documents_doc: Optional[str] = Field(None, max_length=500)


# ============================================================================
# Step 3 — Departments
# ============================================================================

class OnboardingDepartment(BaseModel):
    """Step 3: a department, under a branch (persisted to the departments table)."""
    department_id: UUID = Field(
        ...,
        description="Client-generated UUID (uuid4) for this department. The "
                    "department is created with this id, and divisions/job_codes "
                    "reference it by this same UUID.",
    )
    department_name: str = Field(..., min_length=1, max_length=100)
    entity_id: UUID = Field(
        ...,
        description="UUID of the branch this department belongs to; must match a "
                    "branches[].entity_id (stored as departments.entity_id)",
    )
    department_code: Optional[str] = Field(None, max_length=50)
    department_type: Optional[str] = Field(None, max_length=50, description="departments.department_type")
    cost_center: Optional[str] = Field(None, max_length=50)
    department_head: Optional[str] = Field(None, max_length=100, description="Head / manager")
    location: str = Field(..., max_length=255)
    phone: str = Field(..., max_length=20)
    email: str = Field(..., max_length=255)
    reporting_structure: Optional[str] = Field(None, max_length=100)
    # Required NOT NULL on the departments table; defaults to 0 when the form omits it.
    annual_budget: Decimal = Field(default=Decimal(0))


# ============================================================================
# Step 4 — Divisions
# ============================================================================

class OnboardingDivision(BaseModel):
    """Step 4: a division, under a branch (and optionally a department)."""
    id: UUID = Field(
        ...,
        description="Client-generated UUID (uuid4) for this division (divisions.id). "
                    "job_codes reference it by this same UUID.",
    )
    division_name: str = Field(..., min_length=1, max_length=100)
    division_code: str = Field(..., min_length=1, max_length=20)
    entity_id: UUID = Field(
        ...,
        description="UUID of the branch this division belongs to; must match a "
                    "branches[].entity_id (stored as divisions.entity_id)",
    )
    department_id: Optional[UUID] = Field(
        None,
        description="Optional UUID of the parent department; must match a "
                    "departments[].department_id (stored as divisions.department_id)",
    )
    division_head: Optional[str] = Field(None, max_length=100, description="Head / lead")
    hierarchy_level: Optional[str] = Field("1", max_length=10)
    description: Optional[str] = None


# ============================================================================
# Step 5 — Job codes
# ============================================================================

class OnboardingJobCode(BaseModel):
    """Step 5: a job code / position.

    The jobcode_basicinfo table requires entity, department AND division, so all
    three indices are mandatory here (unlike the looser-looking form).
    """
    job_code: str = Field(..., min_length=1, max_length=50)
    job_title: str = Field(..., min_length=1, max_length=150)
    entity_id: UUID = Field(
        ...,
        description="UUID of the branch this job code belongs to; must match a "
                    "branches[].entity_id (jobcode basic_info entity)",
    )
    department_id: UUID = Field(
        ...,
        description="UUID of the parent department; must match a "
                    "departments[].department_id (jobcode basic_info department)",
    )
    division_id: UUID = Field(
        ...,
        description="UUID of the parent division; must match a divisions[].id "
                    "(jobcode basic_info division)",
    )
    employment_type: Optional[str] = Field(None, max_length=50)
    work_mode: Optional[str] = Field(None, max_length=50)
    grade_band: Optional[str] = Field(None, max_length=50, description="Grade / band")
    minimum_salary: Optional[int] = None
    maximum_salary: Optional[int] = None
    salary_currency: Optional[str] = Field(None, max_length=10, description="Salary currency")
    experience_years: Optional[int] = None
    reports_to: Optional[str] = Field(None, max_length=100, description="Manager job title (basic_info.reports_to)")
    required_skills: Optional[str] = Field(None, description="Stored on jobcode_skills.required_skills")
    key_responsibilities: Optional[str] = Field(None, description="Stored on jobcode_skills.key_responsibilities")


# ============================================================================
# Step 6 — Roles
# ============================================================================

class OnboardingRole(BaseModel):
    """Step 6: a role for this client (user_role + userrole_basic)."""
    id: UUID = Field(
        ...,
        description="Client-generated UUID (uuid4) for this role (user_role.id). "
                    "Other roles (parent_role_id) and users (role_id) reference "
                    "it by this same UUID.",
    )
    role_name: str = Field(..., min_length=1, max_length=100)
    role_code: str = Field(..., min_length=1, max_length=50)
    role_level: int = Field(default=1, description="userrole_basic.role_level")
    parent_role_id: Optional[UUID] = Field(
        None,
        description="Optional UUID of the parent role; must match another "
                    "roles[].id (stored as user_role.parent_role_id)",
    )
    access_scope: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None
    is_admin: bool = Field(default=False, description="Admin role flag")
    default_for_new_users: bool = Field(default=False)
    active: bool = Field(default=True)


# ============================================================================
# Step 7 — Users
# ============================================================================

class OnboardingUser(BaseModel):
    """Step 7: a user (user_setup + usersetup_basic [+ role/entity assignment])."""
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    employee_id: str = Field(..., min_length=1, max_length=50)
    username: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=6)
    phone: Optional[str] = Field(None, max_length=20)
    status: Optional[str] = Field("active", max_length=50)
    role_id: Optional[UUID] = Field(
        None,
        description="Optional UUID of the role to assign; must match a roles[].id",
    )
    entity_id: Optional[UUID] = Field(
        None,
        description="Optional UUID of the branch to grant this user; must match a "
                    "branches[].entity_id. Stored as the user's default_entity "
                    "(and added to entities/assigned_entities).",
    )
    user_group_id: Optional[UUID] = Field(None, description="Optional user group id (bare reference)")
    send_invite_email: bool = Field(default=False, description="Send an invite email to the user")


# ============================================================================
# Request
# ============================================================================

class OnboardingRequest(BaseModel):
    """The full step-form payload submitted by the 'Onboard client' button."""
    company: OnboardingCompany
    branches: List[OnboardingBranch] = Field(default_factory=list)
    departments: List[OnboardingDepartment] = Field(default_factory=list)
    divisions: List[OnboardingDivision] = Field(default_factory=list)
    job_codes: List[OnboardingJobCode] = Field(default_factory=list)
    roles: List[OnboardingRole] = Field(default_factory=list)
    users: List[OnboardingUser] = Field(default_factory=list)
    # Step 8 — Subscription plan (one per client; tenant_id is set from the new tenant)
    subscription: Optional[SubscriptionCreate] = None
    # Step 9 — Security settings (SSO / MFA / session & password policy)
    security: Optional[SecurityCreate] = None


class OnboardingCompanyUpdate(BaseModel):
    """PUT body — updates the client/company (tenant) fields only."""
    client_name: Optional[str] = Field(None, max_length=255)
    client_code: Optional[str] = Field(None, max_length=100)
    industry: Optional[str] = Field(None, max_length=100)
    company_size: Optional[str] = Field(None, max_length=50)
    employees_count: Optional[int] = Field(None, ge=0)
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=500)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    status: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = None


# ============================================================================
# Responses
# ============================================================================

class OnboardingCounts(BaseModel):
    branches: int = 0
    departments: int = 0
    divisions: int = 0
    job_codes: int = 0
    roles: int = 0
    users: int = 0
    subscription: int = 0
    security: int = 0


class OnboardingResult(BaseModel):
    """Returned by POST — what was created."""
    success: bool = True
    message: str = "Client onboarded successfully"
    tenant_id: UUID
    tenant_db_name: Optional[str] = None
    owner_email: str
    counts: OnboardingCounts


class OnboardingSummary(BaseModel):
    """One row in the onboarding list."""
    tenant_id: UUID
    client_name: str = Field(..., validation_alias="tenant_name")
    client_code: Optional[str] = Field(None, validation_alias="tenant_code")
    contact_email: Optional[str] = None
    onboarding_status: Optional[str] = None
    is_active: Optional[bool] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class OnboardingListResponse(BaseModel):
    success: bool = True
    data: List[OnboardingSummary]
    total: int
    page: int = 1
    per_page: int = 10


class _NamedRef(BaseModel):
    id: UUID
    name: str
    code: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class OnboardingDetail(BaseModel):
    """Returned by GET /{tenant_id} — the tenant plus its tenant-DB records."""
    success: bool = True
    tenant_id: UUID
    client_name: str
    client_code: Optional[str] = None
    contact_email: Optional[str] = None
    onboarding_status: Optional[str] = None
    is_active: Optional[bool] = None
    tenant_db_name: Optional[str] = None
    counts: OnboardingCounts
    branches: List[_NamedRef] = Field(default_factory=list)
    departments: List[_NamedRef] = Field(default_factory=list)
    divisions: List[_NamedRef] = Field(default_factory=list)
    job_codes: List[_NamedRef] = Field(default_factory=list)
    roles: List[_NamedRef] = Field(default_factory=list)
    users: List[_NamedRef] = Field(default_factory=list)
