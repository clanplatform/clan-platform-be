"""
Onboarding Pydantic schemas.

The onboarding POST accepts the entire step-form as one graph and creates, in a
single sequence:

    tenant (client)  ->  branches (entities)  ->  departments  ->  divisions
                     ->  job codes  ->  roles  ->  users_groups  ->  users

branches[], departments[], divisions[], job_codes[], roles[] and
users_groups[] all carry a **client-generated UUID** (entity_id,
department_id, division_id, job_code_id, role_id, group_id respectively) —
same as the direct entities/departments/divisions/job_codes/user_role/
users_groups modules' own primary keys — so every child references its
parent(s) by that real UUID. roles[].role_code (already required and unique
per tenant) also doubles as a natural key: a role's PARENT role is
referenced by role_code rather than by role_id (see roles[i].parent_role
below), since a role can't reference itself as its own parent by UUID before
it exists in the same array. users[] references its role/branches/job_code/
group the same way — by real UUID:

    departments[i].entity_id         -> branches[].entity_id            (UUID)
    divisions[i].entity_id           -> branches[].entity_id            (UUID)
    divisions[i].department_id       -> departments[].department_id     (UUID, optional)
    job_codes[i].entity_id           -> branches[].entity_id            (UUID)
    job_codes[i].department_id       -> departments[].department_id     (UUID)
    job_codes[i].division_id         -> divisions[].division_id         (UUID)
    roles[i].parent_role            -> roles[].role_code               (role_code, optional; resolved to that
                                                                           role's real id and stored as
                                                                           user_role.parent_role_id — same
                                                                           mechanism as the direct user_role
                                                                           module's parent_role field)
    users_groups[i].default_role_id  -> roles[].role_id                 (UUID, optional; stored as
                                                                           users_group.default_role_id — same as
                                                                           the direct users_groups module's
                                                                           UserGroupCreate.default_role_id)
    users[i].role_id                 -> roles[].role_id                 (UUID, optional; stored as usersetup_basic.role_id)
    users[i].entity_id               -> branches[].entity_id            (list of UUIDs, optional; the first is the
                                                                           user's default branch; stored as
                                                                           usersetup_basic.entity_id)
    users[i].job_code_id             -> job_codes[].job_code_id         (UUID, optional; stored as
                                                                           usersetup_basic.job_code_id —
                                                                           department_id/division_id are derived
                                                                           from it server-side)
    users[i].user_group_id           -> users_groups[].group_id         (UUID, optional; stored as
                                                                           usersetup_basic.user_group_id)

branches[].entity_id, departments[].department_id, divisions[].division_id,
job_codes[].job_code_id, roles[].role_id, roles[].role_code and
users_groups[].group_id must each be unique within the request. Every
reference is validated server-side by UUID set membership against its
target array (roles[i].parent_role may point at any other role, including
one later in the array — roles are created in two passes so forward
references resolve). An unknown UUID/role_code or a duplicate
client-supplied id returns 422.
"""
from typing import List, Optional
from decimal import Decimal
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, field_validator

from app.subscription.schemas.subscription import SubscriptionCreate
from app.security.schemas.security import SecurityCreate
from app.user_role.schemas.user_role import UserRolePermissionBase, _validate_access_scope


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
    initial_status: Optional[str] = Field(
        "Active", max_length=50,
        description="Initial status (Active / Trial / Pending setup) -> tenants.initial_status "
                    "directly, and tenants.is_active ('Active' => true, anything else => false)",
    )
    internal_notes: Optional[str] = Field(None, description="Notes visible to platform admins only")

    # Owner login — becomes the tenant's first admin user in the tenant DB.
    # The password is never accepted here — it's always randomly generated
    # server-side (see create_onboarding()) and returned once via
    # OnboardingResult.temp_password.
    owner_name: Optional[str] = Field(None, max_length=200, description="Owner administrator full name")
    owner_email: str = Field(..., description="Account-admin (owner) login email; created as the first admin user")


# ============================================================================
# Step 2 — Branches (entities)
# ============================================================================

class OnboardingBranch(BaseModel):
    """Step 2: a branch / legal entity (persisted to the entities table)."""
    entity_id: UUID = Field(
        ...,
        description="Client-generated UUID (uuid4) for this branch/entity — the "
                    "entities table's real primary key. The entity is created with "
                    "this id, and departments/divisions/job_codes/users all "
                    "reference it by this same UUID (e.g. departments[].entity_id, "
                    "users[].entity_id).",
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
        description="Client-generated UUID (uuid4) for this department — the "
                    "departments table's real primary key. The department is "
                    "created with this id, and divisions reference it by this "
                    "same UUID (divisions[].department_id). job_codes still "
                    "reference departments by 0-based index (department_index).",
    )
    department_name: str = Field(..., min_length=1, max_length=100)
    entity_id: UUID = Field(
        ...,
        description="UUID of the branch this department belongs to (entities "
                    "table primary key); must match a branches[].entity_id "
                    "(stored as departments.entity_id) — same as the direct "
                    "departments module's DepartmentCreate.entity_id.",
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
    division_id: UUID = Field(
        ...,
        description="Client-generated UUID (uuid4) for this division — the "
                    "divisions table's real primary key. The division is created "
                    "with this id, and job_codes reference it by this same UUID "
                    "(job_codes[].division_id).",
    )
    division_name: str = Field(..., min_length=1, max_length=100)
    division_code: str = Field(..., min_length=1, max_length=20)
    entity_id: UUID = Field(
        ...,
        description="UUID of the branch this division belongs to (entities "
                    "table primary key); must match a branches[].entity_id "
                    "(stored as divisions.entity_id) — same as the direct "
                    "divisions module's DivisionCreate.entity_id.",
    )
    department_id: Optional[UUID] = Field(
        None,
        description="Optional UUID of the parent department (departments table "
                    "primary key); must match a departments[].department_id "
                    "(stored as divisions.department_id) — same as the direct "
                    "divisions module's DivisionCreate.department_id.",
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
    three ids are mandatory here (unlike the looser-looking form).

    users[].job_code_id references this job code by job_code_id (a real,
    client-generated UUID — same as branches/departments/divisions/roles).
    """
    job_code_id: UUID = Field(
        ...,
        description="Client-generated UUID (uuid4) for this job code — the "
                    "job_codes table's real primary key. The job code is "
                    "created with this id, and users reference it by this "
                    "same UUID (users[].job_code_id).",
    )
    job_code: str = Field(..., min_length=1, max_length=50)
    job_title: str = Field(..., min_length=1, max_length=150)
    entity_id: UUID = Field(
        ...,
        description="UUID of the branch this job code belongs to (entities "
                    "table primary key); must match a branches[].entity_id "
                    "(stored as jobcode_basicinfo.entity_id).",
    )
    department_id: UUID = Field(
        ...,
        description="UUID of the parent department (departments table primary "
                    "key); must match a departments[].department_id (stored as "
                    "jobcode_basicinfo.department_id).",
    )
    division_id: UUID = Field(
        ...,
        description="UUID of the parent division (divisions table primary key); "
                    "must match a divisions[].division_id (stored as "
                    "jobcode_basicinfo.division_id).",
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
    """Step 6: a role for this client (user_role + userrole_basic [+ userrole_permission]).

    users_groups[].default_role_id and users[].role_id both reference this
    role by role_id (a real, client-generated UUID — same as branches/
    departments/divisions/job_codes).
    """
    role_id: UUID = Field(
        ...,
        description="Client-generated UUID (uuid4) for this role — the user_role "
                    "table's real primary key (UserRoleMain.id). The role is "
                    "created with this id, and users_groups reference it by this "
                    "same UUID (users_groups[].default_role_id).",
    )
    role_name: str = Field(..., min_length=1, max_length=100)
    role_code: str = Field(..., min_length=1, max_length=50)
    role_level: int = Field(default=1, description="userrole_basic.role_level")
    parent_role: Optional[str] = Field(
        None, max_length=50,
        description="Parent role's role_code (may point at any other role, "
                    "including one later in this array); must match a "
                    "roles[].role_code in this same request. Resolved to that "
                    "role's real id and stored as user_role.parent_role_id — "
                    "same mechanism as the direct user_role module's "
                    "UserRoleBasicCreate.parent_role.",
    )
    access_scope: Optional[str] = Field(
        None, max_length=50,
        description="Access scope: whole_organization, branch_entity, department, or division",
    )
    description: Optional[str] = None
    is_admin: bool = Field(default=False, description="Admin role flag")
    default_for_new_users: bool = Field(default=False)
    active: bool = Field(default=True)
    permissions: Optional[List[UserRolePermissionBase]] = Field(
        default_factory=list,
        description="Menu / Form / Button access for this role (userrole_permission), "
                    "same shape as the direct Roles screen's Access panel — each entry's "
                    "menu_permissions/form_permissions/button_permissions holds "
                    "PermissionItems keyed by menu/form/button id with an access level "
                    "(read/write/disable). A child menu can never exceed its parent's access.",
    )

    @field_validator("access_scope")
    @classmethod
    def validate_access_scope(cls, v):
        return _validate_access_scope(v)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "role_id": "44444444-4444-4444-4444-444444444444",
                "role_name": "Manager",
                "role_code": "MGR",
                "role_level": 2,
                "parent_role": None,
                "access_scope": "whole_organization",
                "description": "Manager role",
                "is_admin": False,
                "default_for_new_users": False,
                "active": True,
                "permissions": [
                    {
                        "menu_permissions": [
                            {
                                "id": "cd829d19-3ad4-4b43-93dc-855774e3afd0",
                                "application_id": "app-uuid-123",
                                "modules_id": "module-uuid-456",
                                "menu_access": ["write"],
                            },
                            {
                                "id": "c3101217-3fa8-4e5e-8762-92a306c3c7d6",
                                "application_id": "app-uuid-789",
                                "modules_id": "module-uuid-012",
                                "menu_access": ["read"],
                            },
                        ],
                        "button_permissions": [
                            {"id": "9a1c2f7e-1111-4bbb-9ccc-2b6d5e4f7a01", "button_access": ["write"]}
                        ],
                        "form_permissions": [
                            {
                                "id": "8ef5debb-b170-4659-a8ad-a73d41e5365d",
                                "application_id": "app-uuid-123",
                                "modules_id": "module-uuid-456",
                                "form_access": ["write"],
                            }
                        ],
                    }
                ],
            }
        }
    )


# ============================================================================
# Step 7 — User groups
# ============================================================================

class OnboardingUserGroup(BaseModel):
    """Step 7: a user group — bundles users under a shared default role
    (users_group table). Optional; add before users so they can be assigned
    to a group below.

    users[].user_group_id references this group by group_id (a real,
    client-generated UUID — same as branches/departments/divisions/roles/
    job_codes).
    """
    group_id: UUID = Field(
        ...,
        description="Client-generated UUID (uuid4) for this user group — the "
                    "users_group table's real primary key. The group is "
                    "created with this id, and users reference it by this "
                    "same UUID (users[].user_group_id).",
    )
    group_name: str = Field(..., min_length=1, max_length=100)
    group_code: Optional[str] = Field(None, max_length=50)
    default_role_id: Optional[UUID] = Field(
        None,
        description="UUID of the default role for users in this group; must "
                    "match a roles[].role_id (stored as users_group.default_role_id) "
                    "— same as the direct users_groups module's "
                    "UserGroupCreate.default_role_id.",
    )
    description: Optional[str] = None





# ============================================================================
# Step 8 — Users
# ============================================================================

class OnboardingUser(BaseModel):
    """Step 8: a user (user_setup + usersetup_basic [+ role/entity assignment])."""
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    employee_id: str = Field(..., min_length=1, max_length=50)
    username: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=6)
    phone: Optional[str] = Field(None, max_length=20)
    profile_image_url: Optional[str] = Field(None, max_length=500, description="Profile image URL")
    status: Optional[str] = Field("active", max_length=50)
    role_id: Optional[UUID] = Field(
        None,
        description="UUID of the role to assign; must match a roles[].role_id "
                    "(stored as usersetup_basic.role_id) — same as the direct "
                    "user_setup module's UserSetupBasicCreate.role_id.",
    )
    entity_id: Optional[List[UUID]] = Field(
        None,
        description="List of branch UUIDs to grant this user (a user can belong "
                    "to multiple entities); each must match a branches[].entity_id "
                    "(stored as usersetup_basic.entity_id — the first is treated "
                    "as the user's default branch) — same as the direct "
                    "user_setup module's UserSetupBasicCreate.entity_id.",
    )
    job_code_id: Optional[UUID] = Field(
        None,
        description="UUID of the job code to assign this user; must match a "
                    "job_codes[].job_code_id (stored as usersetup_basic.job_code_id "
                    "— department_id/division_id are derived from it server-side, "
                    "not accepted directly here) — same as the direct user_setup "
                    "module's UserSetupBasicCreate.job_code_id.",
    )
    user_group_id: Optional[UUID] = Field(
        None,
        description="UUID of the user group to place this user in; must match a "
                    "users_groups[].group_id (stored as usersetup_basic.user_group_id) "
                    "— same as the direct user_setup module's "
                    "UserSetupBasicCreate.user_group_id.",
    )
    send_invite_email: bool = Field(default=False, description="Send an invite email to the user")


# ============================================================================
# Request
# ============================================================================

class OnboardingRequest(BaseModel):
    """The full, complete step-form payload — every one of the 10 steps
    present. Not the POST /onboarding/ request body itself (see
    OnboardingStepRequest for that): this is what the server assembles by
    merging the step(s) sent across one or more POST calls onto the saved
    draft, and only constructs (re-validating strictly) once that merged
    result is complete, right before actually creating the tenant.

    Not part of the request: if a submission fails partway (validation
    error, duplicate client, etc.), the server generates its own draft_id
    and saves the submitted data under it — see GET/DELETE
    /onboarding/drafts/{draft_id} (returned in the error response).
    """
    company: OnboardingCompany
    branches: List[OnboardingBranch] = Field(default_factory=list)
    departments: List[OnboardingDepartment] = Field(default_factory=list)
    divisions: List[OnboardingDivision] = Field(default_factory=list)
    job_codes: List[OnboardingJobCode] = Field(default_factory=list)
    roles: List[OnboardingRole] = Field(default_factory=list)
    users_groups: List[OnboardingUserGroup] = Field(default_factory=list)
    users: List[OnboardingUser] = Field(default_factory=list)
    # Step 9 — Subscription plan (one per client; tenant_id is set from the new tenant)
    subscription: Optional[SubscriptionCreate] = None
    # Step 10 — Security settings (SSO / MFA / session & password policy)
    security: Optional[SecurityCreate] = None


class OnboardingStepRequest(BaseModel):
    """POST /onboarding/ request body.

    Every field is optional here, unlike OnboardingRequest — a resumed
    submission only needs to include the step(s) being added or changed on
    THIS call. The server merges whichever fields ARE included onto the
    payload already saved under draft_id (see GET /onboarding/drafts/
    {draft_id}); a step left out keeps whatever value an earlier call saved
    for it. Only once the merged result covers all 10 steps is it strictly
    re-validated as a full OnboardingRequest and the tenant actually
    created — so a step that IS included must still be complete on its own
    (e.g. job_codes[] here still requires entity_id/department_id/
    division_id per item); merging only spares you from resending OTHER,
    already-completed steps.

    Note this is step-level, not item-level: resending a step's array
    replaces the previously saved array for that step outright (it does not
    append to it) — a single step's items must all be submitted together.
    """
    company: Optional[OnboardingCompany] = None
    branches: Optional[List[OnboardingBranch]] = None
    departments: Optional[List[OnboardingDepartment]] = None
    divisions: Optional[List[OnboardingDivision]] = None
    job_codes: Optional[List[OnboardingJobCode]] = None
    roles: Optional[List[OnboardingRole]] = None
    users_groups: Optional[List[OnboardingUserGroup]] = None
    users: Optional[List[OnboardingUser]] = None
    subscription: Optional[SubscriptionCreate] = None
    security: Optional[SecurityCreate] = None


class OnboardingUpdate(BaseModel):
    """PUT body — upserts any of the 10 onboarding steps against an already
    -onboarded client. Every field is optional and independent: a step left
    unset (not present in the request JSON) is left untouched; a step that
    IS present is processed as a list of upserts against the tenant's own
    database, keyed by the same id each step already carries in
    OnboardingRequest — an item whose key matches an existing record
    updates it in place, an unmatched key creates a new record, and
    existing records simply not mentioned in this call are left alone
    (no deletes). Company fields are the one exception: they merge onto
    the tenants row field-by-field (exclude_unset), same as before.

    Upsert key per step:
        branches      -> entity_id
        departments   -> department_id
        divisions     -> division_id
        job_codes     -> job_code_id
        roles         -> role_code (NOT role_id — role_code is the tenant
                         -unique natural key; if a role_code in this
                         request already exists under a different role_id,
                         the EXISTING role is updated and its real id is
                         used for any users_groups[]/users[] reference in
                         this same call that pointed at the payload's
                         role_id)
        users_groups  -> group_id
        users         -> email (OnboardingUser has no client-generated id,
                         unlike every other step; usersetup_basic.email is
                         unique per tenant DB)

    Since each step's item is the exact same schema used to CREATE that
    record (OnboardingBranch, OnboardingDepartment, ... OnboardingUser),
    every field the item schema carries is always overwritten on update —
    this is a full-record PUT per item, not a partial per-field patch.
    Notably, users[].password is required, so re-sending an existing user
    always resets their password; roles[].permissions defaults to an empty
    list when omitted, so a role item without permissions clears them.

    is_active is intentionally not here for company fields — same rule as
    TenantUpdate: it's backend-derived from initial_status, never accepted
    directly.
    """
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
    postal_code: Optional[str] = Field(None, max_length=20)
    description: Optional[str] = None
    display_name: Optional[str] = Field(None, max_length=255)
    registration_number: Optional[str] = Field(None, max_length=100)
    tax_id: Optional[str] = Field(None, max_length=100)
    founded_year: Optional[int] = None
    website: Optional[str] = Field(None, max_length=255)
    company_logo: Optional[str] = Field(None, max_length=500)
    annual_revenue: Optional[str] = Field(None, max_length=100)
    contact_name: Optional[str] = Field(None, max_length=255)
    contact_title: Optional[str] = Field(None, max_length=100)
    primary_domain: Optional[str] = Field(None, max_length=100)
    business_model: Optional[str] = Field(None, max_length=100)
    organization_type: Optional[str] = Field(None, max_length=100)
    default_language: Optional[str] = Field(None, max_length=50)
    time_zone: Optional[str] = Field(None, max_length=50)
    default_currency: Optional[str] = Field(None, max_length=10)
    date_format: Optional[str] = Field(None, max_length=20)
    fiscal_year_start: Optional[str] = Field(None, max_length=20)
    week_starts_on: Optional[str] = Field(None, max_length=20)
    initial_status: Optional[str] = Field(None, max_length=50)
    internal_notes: Optional[str] = None
    owner_name: Optional[str] = Field(None, max_length=200)
    owner_email: Optional[str] = None

    # Remaining 9 steps — see the class docstring for the upsert key each
    # one uses. Unset (field absent from the request JSON) = don't touch
    # that step; present = process every item in it as an upsert.
    branches: Optional[List[OnboardingBranch]] = None
    departments: Optional[List[OnboardingDepartment]] = None
    divisions: Optional[List[OnboardingDivision]] = None
    job_codes: Optional[List[OnboardingJobCode]] = None
    roles: Optional[List[OnboardingRole]] = None
    users_groups: Optional[List[OnboardingUserGroup]] = None
    users: Optional[List[OnboardingUser]] = None
    subscription: Optional[SubscriptionCreate] = None
    security: Optional[SecurityCreate] = None


# ============================================================================
# Responses
# ============================================================================

class OnboardingCounts(BaseModel):
    branches: int = 0
    departments: int = 0
    divisions: int = 0
    job_codes: int = 0
    roles: int = 0
    users_groups: int = 0
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
    temp_password: str = Field(
        ...,
        description="Owner's randomly generated temporary password. Returned once — "
                    "must be changed on first login.",
    )
    counts: OnboardingCounts


class OnboardingSummary(BaseModel):
    """One row in the onboarding list."""
    tenant_id: UUID
    client_name: str = Field(..., validation_alias="tenant_name")
    client_code: Optional[str] = Field(None, validation_alias="tenant_code")
    contact_email: Optional[str] = None
    initial_status: Optional[str] = None
    is_active: Optional[bool] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class OnboardingListResponse(BaseModel):
    success: bool = True
    data: List[OnboardingSummary]
    total: int
    page: int = 1
    per_page: int = 10


# ============================================================================
# Drafts — auto-saved when POST /onboarding/ fails partway
# ============================================================================

class OnboardingDraftSummary(BaseModel):
    """One row in the drafts list — no payload (use the detail endpoint for that)."""
    draft_id: UUID
    status: str = Field(..., description="'draft' (still incomplete) or 'completed' (this id went on to onboard successfully)")
    error_message: Optional[str] = None
    tenant_id: Optional[UUID] = Field(None, description="Set once this draft_id successfully onboards")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OnboardingDraftDetail(OnboardingDraftSummary):
    """Returned by GET /onboarding/drafts/{draft_id} — includes the saved payload to resume the form."""
    payload: dict


class OnboardingDraftListResponse(BaseModel):
    success: bool = True
    data: List[OnboardingDraftSummary]
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
    initial_status: Optional[str] = None
    is_active: Optional[bool] = None
    tenant_db_name: Optional[str] = None
    counts: OnboardingCounts
    branches: List[_NamedRef] = Field(default_factory=list)
    departments: List[_NamedRef] = Field(default_factory=list)
    divisions: List[_NamedRef] = Field(default_factory=list)
    job_codes: List[_NamedRef] = Field(default_factory=list)
    roles: List[_NamedRef] = Field(default_factory=list)
    users_groups: List[_NamedRef] = Field(default_factory=list)
    users: List[_NamedRef] = Field(default_factory=list)


class OnboardingStepProgress(BaseModel):
    """One of the 10 onboarding steps and whether it has any data yet."""
    step: str = Field(..., description="Step key, e.g. 'branches'")
    label: str = Field(..., description="Human-readable step name")
    completed: bool = Field(..., description="True once this step's tenant-DB table has at least one row")
    count: int = Field(..., description="How many records exist for this step")


class OnboardingProgress(BaseModel):
    """Returned by GET /{tenant_id}/progress — powers a 'resume onboarding'
    wizard: which of the 10 steps (company, branches, departments, divisions,
    job codes, roles, user groups, users, subscription, security) already
    have data, and which to continue with next."""
    tenant_id: Optional[UUID] = Field(
        None,
        description="Null when computed from a not-yet-created draft payload "
                    "(see POST /onboarding/) — set once a real tenant exists.",
    )
    steps: List[OnboardingStepProgress]
    completed_steps: int
    total_steps: int
    next_step: Optional[str] = Field(None, description="Step key of the first incomplete step, or null once all 10 have data")


class OnboardingDraftSaveResult(BaseModel):
    """Returned by POST /onboarding/.

    While company/branches/departments/divisions/job_codes/subscription/
    roles/users_groups/users/security don't all have data yet, the payload
    is just saved to onboarding_drafts (status 'draft') — no tenant is
    created. Only once every one of the 10 steps is present is the real
    tenant created instead (status 'created') — nothing is optional."""
    status: str = Field(..., description="'draft' (saved, not yet complete) or 'created' (tenant created for real)")
    draft_id: Optional[UUID] = Field(
        None,
        description="Set when status == 'draft' — pass it back as ?draft_id=... on "
                    "the next save to keep updating the same draft instead of "
                    "creating a new one.",
    )
    progress: Optional[OnboardingProgress] = Field(None, description="Set when status == 'draft' — which steps still need data")
    result: Optional[OnboardingResult] = Field(None, description="Set when status == 'created' — the new tenant")
