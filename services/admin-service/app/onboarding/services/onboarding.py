"""
Onboarding service — creates a client (tenant) and its entire org structure in
one sequence.

Flow (POST):
  1. Create the tenant row in the MASTER db and provision its dedicated DB.
  2. In the TENANT db: seed the tenant row (so FKs / get_tenant resolve) and the
     owner admin user, then create branches -> departments -> divisions ->
     job codes -> roles -> user_groups -> users, resolving each child to its
     parent by the client-supplied UUID carried in the payload.

Reuse: branches/departments/divisions/job codes/user_groups go through the
existing per-record services (validation, locale derivation, audit). Roles
and users are written directly (they only need the small subset the step
form collects).

Atomicity: the per-record services commit as they go, so this is NOT a single
transaction. On failure after the tenant is created, the error is surfaced
and the (empty/partial) client can be retried or deleted.
"""
import logging
from typing import Dict, List, Optional, Tuple
from uuid import UUID
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash, generate_temp_password
from app.infrastructure.database.tenant_db_manager import tenant_db_manager

from app.tenants.models.tenants import Tenant

from app.domains.models.domain import Domain
from app.applications.models.application import Application
from app.modules.models.module import Module
from app.menus.models.menu import Menu
from app.forms.models.forms import Form
from app.buttons.models.button import Button

from app.entities.models.entity import Entity
from app.entities.services.entity import create_entity, update_entity
from app.entities.schemas.entity import EntityCreate, EntityUpdate, EntityResponse
from app.departments.models.departments import Department
from app.departments.services.departments import create_department, update_department
from app.departments.schemas.departments import DepartmentCreate, DepartmentUpdate, DepartmentResponse
from app.divisions.models.divisions import Division
from app.divisions.services.divisions import create_division, update_division
from app.divisions.schemas.divisions import DivisionCreate, DivisionUpdate, DivisionResponse
from app.job_codes.models.job_codes import JobCode
from app.job_codes.services.job_codes import create_job_code, update_job_code
from app.job_codes.schemas.job_codes import (
    JobCodeCreate,
    JobCodeUpdate,
    JobCodeBasicInfoCreate,
    JobCodeBasicInfoUpdate,
    JobCodeSkillsCreate,
    JobCodeSkillsUpdate,
    JobCodeRead,
)
from app.user_role.models.user_role import UserRoleMain, UserRoleBasic, UserRolePermission
from app.user_role.services.user_role import UserRoleService
from app.users_groups.models.users_groups import UserGroup
from app.users_groups.services.users_groups import create_user_group, update_user_group
from app.users_groups.schemas.users_groups import UserGroupCreate, UserGroupUpdate, UserGroupResponse
from app.user_setup.models.user_setup import UserSetup, UserSetupBasic
from app.user_setup.schemas.user_setup import UserSetupBasicResponse
from app.subscription.models.subscription import Subscription
from app.subscription.services.subscription import create_subscription, update_subscription
from app.subscription.schemas.subscription import SubscriptionCreate, SubscriptionUpdate, SubscriptionResponse
from app.security.models.security import Security
from app.security.services.security import create_security, update_security
from app.security.schemas.security import SecurityCreate, SecurityUpdate, SecurityResponse

from app.onboarding.models.onboarding import OnboardingDraft
from app.onboarding.schemas.onboarding import (
    OnboardingRequest,
    OnboardingUpdate,
    OnboardingCompany,
    OnboardingBranch,
    OnboardingDepartment,
    OnboardingDivision,
    OnboardingJobCode,
    OnboardingRole,
    OnboardingUserGroup,
    OnboardingUser,
    OnboardingCounts,
    OnboardingDetail,
    OnboardingRoleDetail,
    OnboardingSummary,
    OnboardingListResponse,
    OnboardingDraftSummary,
    OnboardingDraftDetail,
    OnboardingDraftListResponse,
    OnboardingStepProgress,
    OnboardingProgress,
)
from app.onboarding.exceptions import (
    DuplicateTenantError,
    OnboardingUnknownReferenceError,
    OnboardingDuplicateError,
    TenantProvisioningError,
    OnboardingNotFoundError,
    OnboardingDraftNotFoundError,
    OnboardingCreationFailedError,
    OnboardingUpdateFailedError,
)

logger = logging.getLogger(__name__)


def _safe_uuid(value) -> Optional[UUID]:
    try:
        return UUID(str(value)) if value else None
    except (ValueError, TypeError):
        return None


def _filter_fields(schema_cls, source) -> dict:
    """Build a dict of only the fields schema_cls actually declares, pulled
    from a flat Onboarding* item (e.g. OnboardingBranch -> EntityUpdate).
    Safe wherever the target *Create/*Update schema's fields are a strict
    subset of the source item's fields by name (true for entities/
    departments/divisions/user_groups — verified by reading each schema);
    job codes and roles have their own bespoke construction instead (nested
    shape / natural-key + two-table upsert)."""
    return {k: v for k, v in source.model_dump().items() if k in schema_cls.model_fields}


# ============================================================================
# Menu/form/button catalog sync (master -> tenant)
#
# menus/forms/buttons are platform navigation catalog data, managed in the
# master DB, but roles[].permissions in onboarding grant access against a
# tenant's OWN menus/forms/buttons tables (each tenant DB gets its own copy —
# there's no tenant_id column, isolation is per-database). A brand-new
# tenant's copy starts empty, so any menu/form/button id referenced by a
# role's permissions must be copied over from the master DB (preserving the
# same primary key) before UserRoleService's existence checks — which run
# against the tenant DB — can succeed. Tenants only ever get menus/forms/
# buttons this way: copied from the master catalog, never created directly.
# ============================================================================

def _sync_domain(master_db: Session, tenant_db: Session, domain_id: UUID) -> None:
    if tenant_db.query(Domain).filter(Domain.id == domain_id).first():
        return
    row = master_db.query(Domain).filter(Domain.id == domain_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Domain with ID {domain_id} not found")
    tenant_db.add(Domain(**{c.name: getattr(row, c.name) for c in Domain.__table__.columns}))
    tenant_db.flush()


def _sync_application(master_db: Session, tenant_db: Session, application_id: UUID) -> None:
    if tenant_db.query(Application).filter(Application.id == application_id).first():
        return
    row = master_db.query(Application).filter(Application.id == application_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Application with ID {application_id} not found")
    _sync_domain(master_db, tenant_db, row.domain_id)
    tenant_db.add(Application(**{c.name: getattr(row, c.name) for c in Application.__table__.columns}))
    tenant_db.flush()


def _sync_module(master_db: Session, tenant_db: Session, module_id: UUID) -> None:
    if tenant_db.query(Module).filter(Module.id == module_id).first():
        return
    row = master_db.query(Module).filter(Module.id == module_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Module with ID {module_id} not found")
    _sync_application(master_db, tenant_db, row.application_id)
    tenant_db.add(Module(**{c.name: getattr(row, c.name) for c in Module.__table__.columns}))
    tenant_db.flush()


def _sync_menu(master_db: Session, tenant_db: Session, menu_id: UUID) -> None:
    if tenant_db.query(Menu).filter(Menu.id == menu_id).first():
        return
    row = master_db.query(Menu).filter(Menu.id == menu_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Menu with ID {menu_id} not found")
    _sync_application(master_db, tenant_db, row.application_id)
    if row.module_id:
        _sync_module(master_db, tenant_db, row.module_id)
    if row.parent_menu_id:
        _sync_menu(master_db, tenant_db, row.parent_menu_id)
    tenant_db.add(Menu(**{c.name: getattr(row, c.name) for c in Menu.__table__.columns}))
    tenant_db.flush()


def _sync_form(master_db: Session, tenant_db: Session, form_id: UUID) -> None:
    if tenant_db.query(Form).filter(Form.id == form_id).first():
        return
    row = master_db.query(Form).filter(Form.id == form_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Form with ID {form_id} not found")
    _sync_menu(master_db, tenant_db, row.menu_id)
    tenant_db.add(Form(**{c.name: getattr(row, c.name) for c in Form.__table__.columns}))
    tenant_db.flush()


def _sync_button(master_db: Session, tenant_db: Session, button_id: UUID) -> None:
    if tenant_db.query(Button).filter(Button.id == button_id).first():
        return
    row = master_db.query(Button).filter(Button.id == button_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Button with ID {button_id} not found")
    _sync_menu(master_db, tenant_db, row.menu_id)
    tenant_db.add(Button(**{c.name: getattr(row, c.name) for c in Button.__table__.columns}))
    tenant_db.flush()


def _sync_role_permission_catalog(master_db: Session, tenant_db: Session, roles: List[OnboardingRole]) -> None:
    """Copy every menu/form/button (and their application/module/domain/
    parent-menu dependencies) referenced anywhere in roles[].permissions[]
    from the master DB into the tenant DB, preserving primary keys, so the
    role-permission existence checks that run against the tenant DB during
    role creation succeed. Shared by onboarding creation and the PUT
    upsert path (see update_onboarding), both of which only ever need
    this against their own roles[] list."""
    for i, r in enumerate(roles):
        for perm in (r.permissions or []):
            for item in (perm.menu_permissions or []):
                _sync_menu(master_db, tenant_db, _safe_uuid(item.id) or item.id)
            for item in (perm.form_permissions or []):
                _sync_form(master_db, tenant_db, _safe_uuid(item.id) or item.id)
            for item in (perm.button_permissions or []):
                _sync_button(master_db, tenant_db, _safe_uuid(item.id) or item.id)


def _validate_indices(payload: OnboardingRequest) -> None:
    """Fail fast (422) if any child references an unknown UUID.

    branches[], departments[], divisions[], job_codes[], roles[] and
    users_groups[] all carry a client-supplied UUID (entity_id,
    department_id, division_id, job_code_id, role_id, group_id respectively)
    — each must be unique within its list, and every reference a child makes
    to a parent (departments/divisions/job_codes -> branches/departments/
    divisions, users_groups -> roles, users -> roles/branches/job_codes/
    users_groups) is validated here by UUID set membership. roles[].role_code
    also doubles as a natural key (also validated for uniqueness here) so
    roles[].parent_role can reference a sibling role by role_code instead of
    by role_id.
    """
    branch_ids = [b.entity_id for b in payload.branches]
    branch_id_set = set(branch_ids)
    if len(branch_id_set) != len(branch_ids):
        raise OnboardingDuplicateError("branches[].entity_id")

    department_ids = [d.department_id for d in payload.departments]
    department_id_set = set(department_ids)
    if len(department_id_set) != len(department_ids):
        raise OnboardingDuplicateError("departments[].department_id")

    division_ids = [dv.division_id for dv in payload.divisions]
    division_id_set = set(division_ids)
    if len(division_id_set) != len(division_ids):
        raise OnboardingDuplicateError("divisions[].division_id")

    job_code_ids = [j.job_code_id for j in payload.job_codes]
    job_code_id_set = set(job_code_ids)
    if len(job_code_id_set) != len(job_code_ids):
        raise OnboardingDuplicateError("job_codes[].job_code_id")

    role_ids = [r.role_id for r in payload.roles]
    role_id_set = set(role_ids)
    if len(role_id_set) != len(role_ids):
        raise OnboardingDuplicateError("roles[].role_id")

    role_codes = [r.role_code for r in payload.roles]
    role_code_set = set(role_codes)
    if len(role_code_set) != len(role_codes):
        raise OnboardingDuplicateError("roles[].role_code")

    group_ids = [g.group_id for g in payload.users_groups]
    group_id_set = set(group_ids)
    if len(group_id_set) != len(group_ids):
        raise OnboardingDuplicateError("users_groups[].group_id")

    for i, d in enumerate(payload.departments):
        if d.entity_id not in branch_id_set:
            raise OnboardingUnknownReferenceError(f"departments[{i}]", d.entity_id, "branches")
    for i, dv in enumerate(payload.divisions):
        if dv.entity_id not in branch_id_set:
            raise OnboardingUnknownReferenceError(f"divisions[{i}]", dv.entity_id, "branches")
        if dv.department_id is not None and dv.department_id not in department_id_set:
            raise OnboardingUnknownReferenceError(f"divisions[{i}]", dv.department_id, "departments")
    for i, j in enumerate(payload.job_codes):
        if j.entity_id not in branch_id_set:
            raise OnboardingUnknownReferenceError(f"job_codes[{i}]", j.entity_id, "branches")
        if j.department_id not in department_id_set:
            raise OnboardingUnknownReferenceError(f"job_codes[{i}]", j.department_id, "departments")
        if j.division_id not in division_id_set:
            raise OnboardingUnknownReferenceError(f"job_codes[{i}]", j.division_id, "divisions")
    for i, r in enumerate(payload.roles):
        if r.parent_role is not None and r.parent_role not in role_code_set:
            raise OnboardingUnknownReferenceError(f"roles[{i}]", r.parent_role, "roles")
    for i, g in enumerate(payload.users_groups):
        if g.default_role_id is not None and g.default_role_id not in role_id_set:
            raise OnboardingUnknownReferenceError(f"users_groups[{i}]", g.default_role_id, "roles")
    for i, u in enumerate(payload.users):
        if u.role_id is not None and u.role_id not in role_id_set:
            raise OnboardingUnknownReferenceError(f"users[{i}]", u.role_id, "roles")
        for eid in (u.entity_id or []):
            if eid not in branch_id_set:
                raise OnboardingUnknownReferenceError(f"users[{i}]", eid, "branches")
        if u.job_code_id is not None and u.job_code_id not in job_code_id_set:
            raise OnboardingUnknownReferenceError(f"users[{i}]", u.job_code_id, "job_codes")
        if u.user_group_id is not None and u.user_group_id not in group_id_set:
            raise OnboardingUnknownReferenceError(f"users[{i}]", u.user_group_id, "users_groups")


def _build_job_code_basic_info_and_skills(
    j: OnboardingJobCode,
) -> Tuple[JobCodeBasicInfoCreate, Optional[JobCodeSkillsCreate]]:
    """Reshape a flat OnboardingJobCode item into the nested basic_info/
    skills JobCodeCreate expects. Shared by create_onboarding's job_codes
    step and the PUT upsert path (JobCodeUpdate's basic_info/skills are
    field-identical to JobCodeCreate's, so the *Update variants are built
    by re-dumping these same objects — see update_onboarding)."""
    basic_info = JobCodeBasicInfoCreate(
        # j.entity_id / j.department_id / j.division_id are the branch's,
        # department's and division's client-supplied UUIDs — used directly.
        entity_id=j.entity_id,
        department_id=j.department_id,
        division_id=j.division_id,
        employment_type=j.employment_type,
        work_mode=j.work_mode,
        grade_band=j.grade_band,
        minimum_salary=j.minimum_salary,
        maximum_salary=j.maximum_salary,
        salary_currency=j.salary_currency,
        experience_years=j.experience_years,
        reports_to=j.reports_to,
    )
    skills = (
        JobCodeSkillsCreate(
            required_skills=j.required_skills,
            key_responsibilities=j.key_responsibilities,
        )
        if (j.required_skills or j.key_responsibilities) else None
    )
    return basic_info, skills


def _split_full_name(full_name: Optional[str]) -> Tuple[str, str]:
    """Split 'Owner full name' into (first, last); defaults to Account / Owner."""
    parts = (full_name or "").strip().split()
    if not parts:
        return "Account", "Owner"
    if len(parts) == 1:
        return parts[0], parts[0]
    return parts[0], " ".join(parts[1:])


def _cleanup_failed_tenant(master_db: Session, tenant: Tenant) -> None:
    """Best-effort cleanup after a failed onboarding attempt: drop the
    (possibly partially-provisioned) tenant database and remove the
    master-DB tenant row, so the same name/code can be retried cleanly
    instead of being blocked by leftover state. Never raises — failures
    here must not mask the original error the caller is already handling."""
    if tenant.tenant_db_name:
        tenant_db_manager.deprovision(tenant.tenant_db_name, settings.DATABASE_URL)
    try:
        master_db.delete(tenant)
        master_db.commit()
    except Exception:
        master_db.rollback()
        logger.warning(
            "Failed to remove tenant row %s after a failed onboarding attempt",
            tenant.tenant_id, exc_info=True,
        )


def _seed_tenant_row(tenant_db: Session, tenant: Tenant) -> None:
    """Copy the full tenant profile into the tenant DB (satisfies FKs / get_tenant)."""
    tenant_db.add(Tenant(**{
        col.name: getattr(tenant, col.name) for col in Tenant.__table__.columns
    }))
    tenant_db.commit()


def _derive_dept_division_from_job_code(
    tenant_db: Session, job_code_id: Optional[UUID]
) -> Tuple[Optional[List[UUID]], Optional[List[UUID]]]:
    """usersetup_basic.department_id/division_id are never accepted directly
    — they're derived from job_code_id's jobcode_basicinfo row (same rule as
    the direct user_setup CRUD's
    UserSetupService._derive_dept_division_from_job_code). Shared by
    _create_user_row and _update_user_row."""
    if job_code_id is None:
        return None, None
    from app.job_codes.models.job_codes import JobCodeBasicInfo
    info = tenant_db.query(
        JobCodeBasicInfo.department_id, JobCodeBasicInfo.division_id
    ).filter(JobCodeBasicInfo.job_code_id == job_code_id).first()
    if not info:
        return None, None
    department_id = [info.department_id] if info.department_id else None
    division_id = [info.division_id] if info.division_id else None
    return department_id, division_id


def _create_user_row(
    tenant_db: Session,
    *,
    firstname: str,
    lastname: str,
    employee_id: str,
    username: str,
    email: str,
    password: str,
    tenant_id: UUID,
    phone: Optional[str] = None,
    profile_image_url: Optional[str] = None,
    status: str = "active",
    role_id: Optional[UUID] = None,
    entity_id: Optional[List[UUID]] = None,
    job_code_id: Optional[UUID] = None,
    user_group_id: Optional[UUID] = None,
    send_invite_email: bool = False,
) -> Tuple[UUID, UUID]:
    """Create user_setup + usersetup_basic (+ optional role/entity/job code assignment).

    By this point in the onboarding sequence, job_codes have already been
    created (step 5, before users at step 8), so the department/division
    lookup below resolves.
    """
    user_setup = UserSetup()
    tenant_db.add(user_setup)
    tenant_db.flush()

    department_id, division_id = _derive_dept_division_from_job_code(tenant_db, job_code_id)

    basic = UserSetupBasic(
        user_setup_id=user_setup.id,
        firstname=firstname,
        lastname=lastname,
        employee_id=employee_id,
        username=username,
        email=email,
        password_hash=get_password_hash(password),
        phone_number=phone,
        profile_image_url=profile_image_url,
        status=status or "active",
        tenant_id=tenant_id,
        entity_id=entity_id,
        department_id=department_id,
        division_id=division_id,
        job_code_id=job_code_id,
        role_id=role_id,
        user_group_id=user_group_id,
        send_invite_email=send_invite_email,
        is_password_change=False,
        can_change_password=True,
    )
    tenant_db.add(basic)
    tenant_db.commit()
    return user_setup.id, basic.id


def _update_user_row(
    tenant_db: Session,
    existing: UserSetupBasic,
    u: OnboardingUser,
    role_id: Optional[UUID],
) -> None:
    """Update-in-place counterpart to _create_user_row, used when a PUT
    users[] item's email matches an existing usersetup_basic row. Every
    field OnboardingUser carries is overwritten - password_hash is not
    among them, since OnboardingUser has no password field (see
    OnboardingUpdate's docstring); an existing user's password is left
    untouched."""
    department_id, division_id = _derive_dept_division_from_job_code(tenant_db, u.job_code_id)
    existing.firstname = u.first_name
    existing.lastname = u.last_name
    existing.employee_id = u.employee_id
    existing.username = u.username
    existing.phone_number = u.phone
    existing.profile_image_url = u.profile_image_url
    existing.status = u.status or "active"
    existing.entity_id = u.entity_id
    existing.department_id = department_id
    existing.division_id = division_id
    existing.job_code_id = u.job_code_id
    existing.role_id = role_id
    existing.user_group_id = u.user_group_id
    existing.send_invite_email = u.send_invite_email
    tenant_db.add(existing)
    tenant_db.commit()


def create_onboarding(
    master_db: Session,
    payload: OnboardingRequest,
    created_by_user_id: Optional[str] = None,
) -> Tuple[Tenant, OnboardingCounts, str]:
    """Create the tenant + its whole org structure. Returns (tenant, counts, temp_password)."""
    company = payload.company
    # The owner's password is never accepted from the caller — always
    # randomly generated here, used to seed the actual login below, and
    # returned once so the caller can hand it to the owner.
    temp_password = generate_temp_password()

    # Duplicate guard (master DB)
    if master_db.query(Tenant).filter(Tenant.tenant_name == company.client_name).first():
        raise DuplicateTenantError("A client with this name already exists")
    if master_db.query(Tenant).filter(Tenant.contact_email == company.contact_email).first():
        raise DuplicateTenantError("A client with this contact email already exists")
    # tenant_db_name (and thus the whole per-tenant database) is derived from
    # tenant_code alone, lowercased — a case-different duplicate code would
    # silently reuse another tenant's database (see TenantDatabaseManager.
    # make_db_name / _slugify), so this must be checked case-insensitively.
    if company.client_code and master_db.query(Tenant).filter(
        func.lower(Tenant.tenant_code) == company.client_code.lower()
    ).first():
        raise DuplicateTenantError("A client with this code already exists")

    # Validate parent references before creating anything
    _validate_indices(payload)

    # 1. Create tenant row in the master DB
    tenant = Tenant(
        tenant_name=company.client_name,
        tenant_code=company.client_code,
        contact_email=company.contact_email,
        contact_phone=company.contact_phone,
        address=company.address,
        city=company.city,
        state=company.state,
        country=company.country,
        postal_code=company.postal_code,
        industry=company.industry,
        company_size=company.company_size,
        employees_count=company.employees_count,
        description=company.description,
        display_name=company.display_name,
        registration_number=company.registration_number,
        tax_id=company.tax_id,
        founded_year=company.founded_year,
        website=company.website,
        deployed_url=company.deployed_url,
        annual_revenue=company.annual_revenue,
        contact_name=company.contact_name,
        contact_title=company.contact_title,
        primary_domain=company.primary_domain,
        business_model=company.business_model,
        organization_type=company.organization_type,
        default_language=company.default_language,
        time_zone=company.time_zone,
        default_currency=company.default_currency,
        date_format=company.date_format,
        fiscal_year_start=company.fiscal_year_start,
        week_starts_on=company.week_starts_on,
        internal_notes=company.internal_notes,
        company_logo=company.company_logo,
        owner_name=company.owner_name,
        owner_email=company.owner_email,
        owner_password_hash=get_password_hash(temp_password),
        # Active/Trial/Pending setup, as selected on the account-status step.
        initial_status=company.initial_status,
        is_active=(company.initial_status or "active").strip().lower() == "active",
        created_by=_safe_uuid(created_by_user_id),
    )
    master_db.add(tenant)
    master_db.commit()
    master_db.refresh(tenant)

    # The DB name is derived from tenant_code (Tenant.tenant_db_name is a computed
    # property) — a client code is required to provision the dedicated database.
    if not tenant.tenant_db_name:
        _cleanup_failed_tenant(master_db, tenant)
        raise TenantProvisioningError()

    # 2. Provision the tenant's dedicated database (CREATE DB + all tables)
    ok = tenant_db_manager.provision(tenant.tenant_db_name, settings.DATABASE_URL, None)
    if not ok:
        _cleanup_failed_tenant(master_db, tenant)
        raise TenantProvisioningError(tenant.tenant_db_name)

    tenant_db = tenant_db_manager.get_session(tenant.tenant_db_name, settings.DATABASE_URL)
    counts = OnboardingCounts()
    failed = False
    try:
        tenant_id = tenant.tenant_id

        # Seed the tenant row into the tenant DB
        _seed_tenant_row(tenant_db, tenant)

        # Copy every menu/form/button (+ their application/module/domain/
        # parent-menu dependencies) referenced by roles[].permissions[] from
        # the master catalog into this tenant DB — done early so a bad
        # reference fails before branches/departments/etc. are created.
        _sync_role_permission_catalog(master_db, tenant_db, payload.roles)

        # Owner admin user (step 1 "Owner login")
        code = (tenant.tenant_code or str(tenant_id)[:8]).upper()
        owner_first, owner_last = _split_full_name(company.owner_name)
        owner_setup_id, owner_basic_id = _create_user_row(
            tenant_db,
            firstname=owner_first,
            lastname=owner_last,
            employee_id=f"OWNER-{code}",
            username=company.owner_email.split("@")[0],
            email=company.owner_email,
            password=temp_password,
            tenant_id=tenant_id,
        )
        counts.users += 1

        # 3. Branches (entities) — created with the client-supplied entity_id so
        #    departments/divisions/job_codes/users can all reference them by
        #    that UUID directly.
        branch_ids: List[UUID] = []
        for b in payload.branches:
            entity = create_entity(
                tenant_db,
                EntityCreate(
                    entity_name=b.entity_name,
                    entity_code=b.entity_code,
                    company_size=b.company_size,
                    contact=b.contact,
                    email=b.email,
                    address_1=b.address_1,
                    address_2=b.address_2,
                    city=b.city,
                    state=b.state,
                    country=b.country,
                    time_zone=b.time_zone,
                    location_type=b.location_type,
                    is_headquarters=b.is_headquarters,
                    phone=b.phone,
                    tax_registration=b.tax_registration,
                    postal_code=b.postal_code,
                    working_days=b.working_days,
                    business_hours_start=b.business_hours_start,
                    business_hours_end=b.business_hours_end,
                    observes_dst=b.observes_dst,
                    business_registration_doc=b.business_registration_doc,
                    tax_certificate_doc=b.tax_certificate_doc,
                    incorporation_certificate_doc=b.incorporation_certificate_doc,
                    data_processing_agreement_doc=b.data_processing_agreement_doc,
                    insurance_certificate_doc=b.insurance_certificate_doc,
                    other_documents_doc=b.other_documents_doc,
                ),
                tenant_id=tenant_id,
                user_id=_safe_uuid(created_by_user_id),
                entity_id=b.entity_id,
            )
            branch_ids.append(entity.entity_id)
        counts.branches = len(branch_ids)

        # 4. Departments
        department_ids: List[UUID] = []
        for d in payload.departments:
            dept = create_department(
                tenant_db,
                DepartmentCreate(
                    department_name=d.department_name,
                    # d.entity_id is the branch's client-supplied UUID
                    # (validated to exist among branches) — used directly.
                    entity_id=d.entity_id,
                    department_code=d.department_code,
                    department_type=d.department_type,
                    cost_center=d.cost_center,
                    department_head=d.department_head,
                    location=d.location,
                    phone=d.phone,
                    email=d.email,
                    reporting_structure=d.reporting_structure,
                    annual_budget=d.annual_budget,
                ),
                tenant_id=tenant_id,
                user_id=_safe_uuid(created_by_user_id),
                department_id=d.department_id,
            )
            department_ids.append(dept.department_id)
        counts.departments = len(department_ids)

        # 5. Divisions
        division_ids: List[UUID] = []
        for dv in payload.divisions:
            division = create_division(
                tenant_db,
                DivisionCreate(
                    division_name=dv.division_name,
                    division_code=dv.division_code,
                    # dv.entity_id / dv.department_id are the branch's and
                    # department's client-supplied UUIDs (validated to exist
                    # among branches/departments) — used directly.
                    entity_id=dv.entity_id,
                    department_id=dv.department_id,
                    division_head=dv.division_head,
                    hierarchy_level=dv.hierarchy_level,
                    description=dv.description,
                ),
                tenant_id=tenant_id,
                user_id=_safe_uuid(created_by_user_id),
                division_id=dv.division_id,
            )
            division_ids.append(division.id)
        counts.divisions = len(division_ids)

        # 6. Job codes
        job_code_ids: List[UUID] = []
        for j in payload.job_codes:
            basic_info, skills = _build_job_code_basic_info_and_skills(j)
            job_code = create_job_code(
                tenant_db,
                JobCodeCreate(job_code=j.job_code, job_title=j.job_title, basic_info=basic_info, skills=skills),
                tenant_id=tenant_id,
                user_id=_safe_uuid(created_by_user_id),
                job_code_id=j.job_code_id,
            )
            job_code_ids.append(job_code.id)
        counts.job_codes = len(job_code_ids)

        # 7. Roles (+ their userrole_permission — Menu/Form/Button access).
        # Two passes: parent_role may point at any role regardless of array
        # order (including one later in the array), so every UserRoleMain
        # (and its real id) must exist before any UserRoleBasic sets
        # parent_role_id.
        role_ids: List[UUID] = []
        role_mains: List[UserRoleMain] = []
        role_code_to_id: Dict[str, UUID] = {}
        for r in payload.roles:
            # r.role_id is the client-supplied UUID (users_groups reference it
            # directly as default_role_id) — used as UserRoleMain's real pk.
            main = UserRoleMain(id=r.role_id)
            tenant_db.add(main)
            tenant_db.flush()
            role_mains.append(main)
            role_ids.append(main.id)
            role_code_to_id[r.role_code] = main.id

        admin_role_id: Optional[UUID] = None
        for r, main in zip(payload.roles, role_mains):
            basic = UserRoleBasic(
                user_role_id=main.id,
                tenant_id=tenant_id,
                role_name=r.role_name,
                role_code=r.role_code,
                description=r.description,
                role_level=r.role_level,
                # r.parent_role is the parent's role_code (validated to exist
                # among roles[] in _validate_indices); resolved to that
                # role's real id via the map built above.
                parent_role_id=(
                    role_code_to_id.get(r.parent_role)
                    if r.parent_role is not None else None
                ),
                access_scope=r.access_scope,
                is_admin=r.is_admin,
                default_for_new_users=r.default_for_new_users,
                active=r.active,
            )
            tenant_db.add(basic)
            tenant_db.flush()  # Get basic.id for the permission rows below

            for perm_data in (r.permissions or []):
                tenant_db.add(
                    UserRoleService.build_permission_row(tenant_db, perm_data, main.id, basic.id)
                )

            if admin_role_id is None and r.is_admin:
                admin_role_id = main.id
        if role_ids:
            tenant_db.commit()
        counts.roles = len(role_ids)

        # Give the owner an admin role when one was created
        if admin_role_id is not None:
            owner_basic = tenant_db.query(UserSetupBasic).filter(UserSetupBasic.id == owner_basic_id).first()
            if owner_basic:
                owner_basic.role_id = admin_role_id
                tenant_db.commit()

        # 8. User groups
        user_group_ids: List[UUID] = []
        for g in payload.users_groups:
            group = create_user_group(
                tenant_db,
                UserGroupCreate(
                    group_name=g.group_name,
                    group_code=g.group_code,
                    # g.default_role_id is the role's client-supplied UUID
                    # (validated to exist among roles[]) — used directly.
                    default_role_id=g.default_role_id,
                    description=g.description,
                ),
                tenant_id=tenant_id,
                user_id=_safe_uuid(created_by_user_id),
                group_id=g.group_id,
            )
            user_group_ids.append(group.id)
        counts.users_groups = len(user_group_ids)

        # 9. Users
        for u in payload.users:
            _create_user_row(
                tenant_db,
                firstname=u.first_name,
                lastname=u.last_name,
                employee_id=u.employee_id,
                username=u.username,
                email=u.email,
                # Always server-generated — OnboardingUser has no password
                # field. Never emailed; not returned in the API response.
                password=generate_temp_password(),
                tenant_id=tenant_id,
                phone=u.phone,
                profile_image_url=u.profile_image_url,
                status=u.status or "active",
                # u.role_id / u.entity_id / u.job_code_id / u.user_group_id are
                # the role's, branches', job code's and group's client-supplied
                # UUIDs (validated to exist among roles/branches/job_codes/
                # users_groups) — used directly.
                role_id=u.role_id,
                entity_id=u.entity_id,
                job_code_id=u.job_code_id,
                user_group_id=u.user_group_id,
                send_invite_email=u.send_invite_email,
            )
            counts.users += 1

        # 10. Subscription plan (optional; one per client)
        if payload.subscription is not None:
            create_subscription(
                tenant_db,
                payload.subscription,
                tenant_id=tenant_id,
                user_id=_safe_uuid(created_by_user_id),
            )
            counts.subscription = 1

        # 11. Security settings (optional; one per client)
        if payload.security is not None:
            create_security(
                tenant_db,
                payload.security,
                tenant_id=tenant_id,
                user_id=_safe_uuid(created_by_user_id),
            )
            counts.security = 1

    except HTTPException:
        tenant_db.rollback()
        failed = True
        raise
    except Exception as exc:
        # Anything that isn't already a clean HTTPException here is a
        # database-level failure (e.g. a stale owner row from a previously
        # deleted tenant colliding on employee_id) — its str() carries the
        # raw SQL + bound parameters, which must not reach the client as-is.
        tenant_db.rollback()
        failed = True
        logger.error(
            "Unexpected error onboarding tenant %s: %s", tenant.tenant_id, exc, exc_info=True
        )
        raise OnboardingCreationFailedError() from exc
    finally:
        tenant_db.close()
        if failed:
            # A failed attempt must not leave a half-created tenant behind —
            # branches/departments/divisions/job_codes etc. commit as they
            # go (see module docstring), so a late failure (e.g. roles)
            # still leaves real data sitting in the tenant DB otherwise.
            _cleanup_failed_tenant(master_db, tenant)

    master_db.refresh(tenant)
    return tenant, counts, temp_password


# ============================================================================
# PUT /{tenant_id} — per-step upsert helpers
#
# Each helper below upserts one onboarding step's array against an already
# -provisioned tenant DB: an item whose key matches an existing record
# updates it in place (via that module's own update_* service — same
# validation the direct CRUD endpoint runs), an unmatched key creates a new
# record (via create_*, honoring the client-supplied UUID exactly like
# create_onboarding does). No deletes. See OnboardingUpdate's docstring for
# the upsert key per step.
# ============================================================================

def _upsert_branches(tenant_db: Session, tenant_id: UUID, branches: List[OnboardingBranch], user_id: Optional[UUID]) -> None:
    for b in branches:
        existing = tenant_db.query(Entity).filter(Entity.entity_id == b.entity_id).first()
        if existing:
            update_entity(tenant_db, b.entity_id, EntityUpdate(**_filter_fields(EntityUpdate, b)), user_id)
        else:
            create_entity(
                tenant_db, EntityCreate(**_filter_fields(EntityCreate, b)),
                tenant_id=tenant_id, user_id=user_id, entity_id=b.entity_id,
            )


def _upsert_departments(tenant_db: Session, tenant_id: UUID, departments: List[OnboardingDepartment], user_id: Optional[UUID]) -> None:
    for d in departments:
        existing = tenant_db.query(Department).filter(Department.department_id == d.department_id).first()
        if existing:
            update_department(tenant_db, d.department_id, DepartmentUpdate(**_filter_fields(DepartmentUpdate, d)), user_id)
        else:
            create_department(
                tenant_db, DepartmentCreate(**_filter_fields(DepartmentCreate, d)),
                tenant_id=tenant_id, user_id=user_id, department_id=d.department_id,
            )


def _upsert_divisions(tenant_db: Session, tenant_id: UUID, divisions: List[OnboardingDivision], user_id: Optional[UUID]) -> None:
    for dv in divisions:
        existing = tenant_db.query(Division).filter(Division.id == dv.division_id).first()
        if existing:
            update_division(tenant_db, dv.division_id, DivisionUpdate(**_filter_fields(DivisionUpdate, dv)), user_id)
        else:
            create_division(
                tenant_db, DivisionCreate(**_filter_fields(DivisionCreate, dv)),
                tenant_id=tenant_id, user_id=user_id, division_id=dv.division_id,
            )


def _upsert_job_codes(tenant_db: Session, tenant_id: UUID, job_codes: List[OnboardingJobCode], user_id: Optional[UUID]) -> None:
    for j in job_codes:
        basic_info, skills = _build_job_code_basic_info_and_skills(j)
        existing = tenant_db.query(JobCode).filter(JobCode.id == j.job_code_id).first()
        if existing:
            update_job_code(
                tenant_db, j.job_code_id,
                JobCodeUpdate(
                    job_code=j.job_code, job_title=j.job_title,
                    basic_info=JobCodeBasicInfoUpdate(**basic_info.model_dump()),
                    skills=JobCodeSkillsUpdate(**skills.model_dump()) if skills else None,
                ),
                user_id,
            )
        else:
            create_job_code(
                tenant_db,
                JobCodeCreate(job_code=j.job_code, job_title=j.job_title, basic_info=basic_info, skills=skills),
                tenant_id=tenant_id, user_id=user_id, job_code_id=j.job_code_id,
            )


def _upsert_roles(tenant_db: Session, tenant_id: UUID, roles: List[OnboardingRole]) -> Dict[UUID, UUID]:
    """Upsert roles keyed by role_code (the tenant-unique natural key — see
    OnboardingUpdate's docstring), two passes exactly like create_onboarding's
    role step: pass 1 resolves/creates/updates each role's own fields
    (deferring parent_role_id and permissions), pass 2 resolves
    parent_role_id (via UserRoleService._resolve_parent_role_id, which
    queries the tenant DB directly by role_code — so it transparently covers
    both a sibling role created earlier in pass 1 of THIS call and a
    pre-existing parent not included in this call at all) and replaces
    permissions wholesale.

    Returns submitted_to_real: payload role_id -> the role's real
    user_role_id. Identical for every role unless this call matched an
    existing role by role_code under a DIFFERENT id than the payload
    supplied — callers MUST translate users_groups[].default_role_id /
    users[].role_id through this map (`.get(id, id)`) before writing them,
    since those fields reference role_id, not role_code.
    """
    role_code_to_id: Dict[str, UUID] = {}
    submitted_to_real: Dict[UUID, UUID] = {}
    basic_rows: Dict[str, UserRoleBasic] = {}

    for r in roles:
        existing_basic = tenant_db.query(UserRoleBasic).filter(
            UserRoleBasic.tenant_id == tenant_id, UserRoleBasic.role_code == r.role_code
        ).first()
        if existing_basic:
            real_id = existing_basic.user_role_id
            existing_basic.role_name = r.role_name
            existing_basic.role_level = r.role_level
            existing_basic.description = r.description
            existing_basic.access_scope = r.access_scope
            existing_basic.is_admin = r.is_admin
            existing_basic.default_for_new_users = r.default_for_new_users
            existing_basic.active = r.active
            basic_row = existing_basic
        else:
            real_id = r.role_id
            main = UserRoleMain(id=real_id)
            tenant_db.add(main)
            tenant_db.flush()
            basic_row = UserRoleBasic(
                user_role_id=main.id,
                tenant_id=tenant_id,
                role_name=r.role_name,
                role_code=r.role_code,
                description=r.description,
                role_level=r.role_level,
                access_scope=r.access_scope,
                is_admin=r.is_admin,
                default_for_new_users=r.default_for_new_users,
                active=r.active,
            )
            tenant_db.add(basic_row)
        tenant_db.flush()
        role_code_to_id[r.role_code] = real_id
        submitted_to_real[r.role_id] = real_id
        basic_rows[r.role_code] = basic_row

    for r in roles:
        basic_row = basic_rows[r.role_code]
        basic_row.parent_role_id = (
            UserRoleService._resolve_parent_role_id(tenant_db, tenant_id, r.parent_role)
            if r.parent_role is not None else None
        )
        tenant_db.query(UserRolePermission).filter(
            UserRolePermission.user_role_id == role_code_to_id[r.role_code]
        ).delete()
        for perm_data in (r.permissions or []):
            tenant_db.add(
                UserRoleService.build_permission_row(tenant_db, perm_data, role_code_to_id[r.role_code], basic_row.id)
            )

    tenant_db.commit()
    return submitted_to_real


def _upsert_user_groups(
    tenant_db: Session, tenant_id: UUID, groups: List[OnboardingUserGroup],
    role_translation: Dict[UUID, UUID], user_id: Optional[UUID],
) -> None:
    for g in groups:
        default_role_id = role_translation.get(g.default_role_id, g.default_role_id) if g.default_role_id else None
        existing = tenant_db.query(UserGroup).filter(UserGroup.id == g.group_id).first()
        if existing:
            update_user_group(
                tenant_db, g.group_id,
                UserGroupUpdate(group_name=g.group_name, group_code=g.group_code,
                                 default_role_id=default_role_id, description=g.description),
                user_id,
            )
        else:
            create_user_group(
                tenant_db,
                UserGroupCreate(group_name=g.group_name, group_code=g.group_code,
                                 default_role_id=default_role_id, description=g.description),
                tenant_id=tenant_id, user_id=user_id, group_id=g.group_id,
            )


def _upsert_users(
    tenant_db: Session, tenant_id: UUID, users: List[OnboardingUser], role_translation: Dict[UUID, UUID],
) -> None:
    """Keyed by email — OnboardingUser has no client-generated id, unlike
    every other step (see OnboardingUpdate's docstring); usersetup_basic
    .email is unique per tenant DB."""
    for u in users:
        role_id = role_translation.get(u.role_id, u.role_id) if u.role_id else None
        existing = tenant_db.query(UserSetupBasic).filter(UserSetupBasic.email == u.email).first()
        if existing:
            _update_user_row(tenant_db, existing, u, role_id)
        else:
            _create_user_row(
                tenant_db,
                firstname=u.first_name, lastname=u.last_name, employee_id=u.employee_id,
                # Always server-generated — OnboardingUser has no password
                # field. Never emailed; not returned in the API response.
                username=u.username, email=u.email, password=generate_temp_password(), tenant_id=tenant_id,
                phone=u.phone, profile_image_url=u.profile_image_url, status=u.status or "active",
                role_id=role_id, entity_id=u.entity_id, job_code_id=u.job_code_id,
                user_group_id=u.user_group_id, send_invite_email=u.send_invite_email,
            )


def _upsert_subscription(tenant_db: Session, tenant_id: UUID, subscription: SubscriptionCreate, user_id: Optional[UUID]) -> None:
    """One row per tenant DB by convention (no DB-level unique constraint —
    same convention create_onboarding/get_onboarding already rely on)."""
    existing = tenant_db.query(Subscription).first()
    if existing:
        update_subscription(tenant_db, existing.subscription_id, SubscriptionUpdate(**subscription.model_dump()), user_id)
    else:
        create_subscription(tenant_db, subscription, tenant_id=tenant_id, user_id=user_id)


def _upsert_security(tenant_db: Session, tenant_id: UUID, security: SecurityCreate, user_id: Optional[UUID]) -> None:
    """One row per tenant DB by convention — same as _upsert_subscription."""
    existing = tenant_db.query(Security).first()
    if existing:
        update_security(tenant_db, existing.security_id, SecurityUpdate(**security.model_dump()), user_id)
    else:
        create_security(tenant_db, security, tenant_id=tenant_id, user_id=user_id)


def list_onboardings(
    master_db: Session,
    page: int = 1,
    size: int = 10,
    search: Optional[str] = None,
) -> OnboardingListResponse:
    """List onboarded clients (tenants) from the master DB."""
    query = master_db.query(Tenant)
    if search:
        query = query.filter(Tenant.tenant_name.ilike(f"%{search}%"))
    total = query.count()
    rows = query.order_by(Tenant.created_at.desc()).offset((page - 1) * size).limit(size).all()
    return OnboardingListResponse(
        data=[OnboardingSummary.model_validate(r) for r in rows],
        total=total,
        page=page,
        per_page=size,
    )


def get_onboarding(master_db: Session, tenant_id: UUID) -> OnboardingDetail:
    """Return the tenant's full profile plus every record in its tenant DB,
    each in the same shape that domain's own GET endpoint returns."""
    tenant = master_db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
    if not tenant:
        raise OnboardingNotFoundError()

    counts = OnboardingCounts()
    branches: List[EntityResponse] = []
    departments: List[DepartmentResponse] = []
    divisions: List[DivisionResponse] = []
    job_codes: List[JobCodeRead] = []
    roles: List[OnboardingRoleDetail] = []
    users_groups: List[UserGroupResponse] = []
    users: List[UserSetupBasicResponse] = []
    subscription: Optional[SubscriptionResponse] = None
    security: Optional[SecurityResponse] = None

    if tenant.tenant_db_name:
        tdb = tenant_db_manager.get_session(tenant.tenant_db_name, settings.DATABASE_URL)
        try:
            branches = [
                EntityResponse.model_validate(e)
                for e in tdb.query(Entity).filter(Entity.deleted == False).all()  # noqa: E712
            ]
            departments = [
                DepartmentResponse.model_validate(d)
                for d in tdb.query(Department).filter(Department.is_deleted == False).all()  # noqa: E712
            ]
            divisions = [
                DivisionResponse.model_validate(dv)
                for dv in tdb.query(Division).filter(Division.deleted_at.is_(None)).all()
            ]
            job_codes = [
                JobCodeRead.model_validate(j)
                for j in tdb.query(JobCode).filter(JobCode.deleted_at.is_(None)).all()
            ]
            role_rows = tdb.query(UserRoleBasic).all()
            # parent_role (role_code) is resolved and stashed onto each row in
            # memory here — same trick UserRoleService's own list/get use — so
            # OnboardingRoleDetail.model_validate(from_attributes) can pick it
            # up alongside the real parent_role_id column. role_id comes
            # straight off the row's own user_role_id column (see
            # OnboardingRoleDetail's docstring for why that, not id, is what
            # users[].role_id / users_groups[].default_role_id match against).
            UserRoleService._attach_parent_role_codes(tdb, role_rows)
            roles = [OnboardingRoleDetail.model_validate(r) for r in role_rows]
            users_groups = [
                UserGroupResponse.model_validate(g)
                for g in tdb.query(UserGroup).filter(UserGroup.deleted_at.is_(None)).all()
            ]
            users = [
                UserSetupBasicResponse.model_validate(u)
                for u in tdb.query(UserSetupBasic).all()
            ]
            # One row per tenant DB by convention (no DB-level unique
            # constraint — same convention _upsert_subscription/_upsert_security
            # already rely on).
            subscription_row = tdb.query(Subscription).first()
            security_row = tdb.query(Security).first()
            subscription = SubscriptionResponse.model_validate(subscription_row) if subscription_row else None
            security = SecurityResponse.model_validate(security_row) if security_row else None
        finally:
            tdb.close()

    counts.branches = len(branches)
    counts.departments = len(departments)
    counts.divisions = len(divisions)
    counts.job_codes = len(job_codes)
    counts.roles = len(roles)
    counts.users_groups = len(users_groups)
    counts.users = len(users)
    counts.subscription = 1 if subscription else 0
    counts.security = 1 if security else 0

    return OnboardingDetail(
        tenant_id=tenant.tenant_id,
        company=OnboardingCompany(
            client_name=tenant.tenant_name,
            client_code=tenant.tenant_code,
            industry=tenant.industry,
            company_size=tenant.company_size,
            employees_count=tenant.employees_count,
            contact_email=tenant.contact_email,
            contact_phone=tenant.contact_phone,
            address=tenant.address,
            city=tenant.city,
            state=tenant.state,
            country=tenant.country,
            postal_code=tenant.postal_code,
            description=tenant.description,
            display_name=tenant.display_name,
            registration_number=tenant.registration_number,
            tax_id=tenant.tax_id,
            founded_year=tenant.founded_year,
            website=tenant.website,
            deployed_url=tenant.deployed_url,
            annual_revenue=tenant.annual_revenue,
            company_logo=tenant.company_logo,
            contact_name=tenant.contact_name,
            contact_title=tenant.contact_title,
            primary_domain=tenant.primary_domain,
            business_model=tenant.business_model,
            organization_type=tenant.organization_type,
            default_language=tenant.default_language,
            time_zone=tenant.time_zone,
            default_currency=tenant.default_currency,
            date_format=tenant.date_format,
            fiscal_year_start=tenant.fiscal_year_start,
            week_starts_on=tenant.week_starts_on,
            internal_notes=tenant.internal_notes,
            owner_name=tenant.owner_name,
            owner_email=tenant.owner_email,
            initial_status=tenant.initial_status,
        ),
        is_active=tenant.is_active,
        tenant_db_name=tenant.tenant_db_name,
        counts=counts,
        branches=branches,
        departments=departments,
        divisions=divisions,
        job_codes=job_codes,
        roles=roles,
        users_groups=users_groups,
        users=users,
        subscription=subscription,
        security=security,
    )


# The 10 onboarding steps, in wizard order.
_PROGRESS_STEPS = [
    ("company", "Company"),
    ("branches", "Branches"),
    ("departments", "Departments"),
    ("divisions", "Divisions"),
    ("job_codes", "Job Codes"),
    ("roles", "Roles"),
    ("users_groups", "User Groups"),
    ("users", "Users"),
    ("subscription", "Subscription"),
    ("security", "Security"),
]



def _build_progress(
    step_counts: Dict[str, int], tenant_id: Optional[UUID], company_present: bool = True
) -> OnboardingProgress:
    """Shared step/completed/next_step assembly for both the DB-backed
    (get_onboarding_progress) and merged-draft-based (compute_dict_progress)
    progress views. company_present defaults True because a real tenant row
    (the DB-backed path) always has company data by construction; the
    merged-draft path passes the actual presence check since company may
    still be unset there."""
    steps: List[OnboardingStepProgress] = []
    next_step: Optional[str] = None
    completed_steps = 0
    for key, label in _PROGRESS_STEPS:
        if key == "company":
            completed, count = company_present, (1 if company_present else 0)
        else:
            count = step_counts[key]
            completed = count > 0
        steps.append(OnboardingStepProgress(step=key, label=label, completed=completed, count=count))
        if completed:
            completed_steps += 1
        elif next_step is None:
            next_step = key

    return OnboardingProgress(
        tenant_id=tenant_id,
        steps=steps,
        completed_steps=completed_steps,
        total_steps=len(_PROGRESS_STEPS),
        next_step=next_step,
    )


def get_onboarding_progress(master_db: Session, tenant_id: UUID) -> OnboardingProgress:
    """Which of the 10 onboarding steps have at least one record yet, and
    which to continue with next — powers a 'resume onboarding' wizard.

    company is always complete once the tenant row exists; every other step
    is complete once its tenant-DB table has at least one row.
    """
    tenant = master_db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
    if not tenant:
        raise OnboardingNotFoundError()

    step_counts: Dict[str, int] = {key: 0 for key, _ in _PROGRESS_STEPS if key != "company"}
    if tenant.tenant_db_name:
        tdb = tenant_db_manager.get_session(tenant.tenant_db_name, settings.DATABASE_URL)
        try:
            step_counts["branches"] = tdb.query(Entity).filter(Entity.deleted == False).count()  # noqa: E712
            step_counts["departments"] = tdb.query(Department).filter(Department.is_deleted == False).count()  # noqa: E712
            step_counts["divisions"] = tdb.query(Division).filter(Division.deleted_at.is_(None)).count()
            step_counts["job_codes"] = tdb.query(JobCode).filter(JobCode.deleted_at.is_(None)).count()
            step_counts["roles"] = tdb.query(UserRoleBasic).count()
            step_counts["users_groups"] = tdb.query(UserGroup).filter(UserGroup.deleted_at.is_(None)).count()
            step_counts["users"] = tdb.query(UserSetupBasic).count()
            step_counts["subscription"] = tdb.query(Subscription).count()
            step_counts["security"] = tdb.query(Security).count()
        finally:
            tdb.close()

    return _build_progress(step_counts, tenant.tenant_id)


def merge_onboarding_payload(master_db: Session, draft_id: UUID, incoming: dict) -> dict:
    """Merge the step keys present in `incoming` (only the fields THIS POST
    call actually included — see OnboardingStepRequest, built via
    payload.model_dump(exclude_unset=True)) onto the payload already saved
    under draft_id, if any.

    Step-level granularity: a step present in `incoming` replaces the saved
    value for that step outright; a step absent from `incoming` keeps
    whatever an earlier call saved for it. This is what lets a resumed
    submission include only the new/changed steps instead of resending
    everything collected so far.
    """
    draft = master_db.query(OnboardingDraft).filter(OnboardingDraft.draft_id == draft_id).first()
    merged = dict(draft.payload) if draft is not None and draft.payload else {}
    merged.update(incoming)
    return merged


def compute_dict_progress(merged: dict) -> OnboardingProgress:
    """Same 10-step shape as get_onboarding_progress(), computed directly
    from a merged (possibly still partial, accumulated across POST calls)
    draft payload dict — no tenant/DB lookup, no OnboardingRequest validation."""
    step_counts = {
        "branches": len(merged.get("branches") or []),
        "departments": len(merged.get("departments") or []),
        "divisions": len(merged.get("divisions") or []),
        "job_codes": len(merged.get("job_codes") or []),
        "roles": len(merged.get("roles") or []),
        "users_groups": len(merged.get("users_groups") or []),
        "users": len(merged.get("users") or []),
        "subscription": 1 if merged.get("subscription") else 0,
        "security": 1 if merged.get("security") else 0,
    }
    return _build_progress(step_counts, tenant_id=None, company_present=bool(merged.get("company")))


def is_progress_complete(progress: OnboardingProgress) -> bool:
    """True once all 10 onboarding steps have data — matches the wizard's own
    step list (Client, Organization, Structure, Job codes, Subscription,
    Roles, Users, Security; Review is just the confirm screen, not a data
    step). Nothing is optional: the tenant + its database are only created
    once every step is complete."""
    return progress.completed_steps == progress.total_steps


# Map OnboardingUpdate field -> Tenant column
_UPDATE_FIELD_MAP = {
    "client_name": "tenant_name",
    "client_code": "tenant_code",
}

# The 9 non-company steps OnboardingUpdate carries — iterated separately
# against the tenant DB ("company" is handled on its own, see below).
_UPDATE_STEP_FIELDS = (
    "branches", "departments", "divisions", "job_codes", "roles",
    "users_groups", "users", "subscription", "security",
)


def update_onboarding(
    master_db: Session,
    tenant_id: UUID,
    update: OnboardingUpdate,
    updated_by_user_id: Optional[str] = None,
) -> Tuple[Tenant, OnboardingDetail]:
    """Update an onboarded client: company/tenant fields (as before) plus,
    now, any of the other 9 onboarding steps — each upserted against the
    tenant's own database via the _upsert_* helpers above (see
    OnboardingUpdate's docstring for the exact semantics: upsert by key,
    no deletes, every item is a full-record replace).

    Same non-atomicity caveat as create_onboarding: the per-record services
    each commit internally, so a failure partway through the tenant-DB step
    processing leaves whatever ran before it committed — this is an update
    to an already-provisioned tenant, so (unlike create_onboarding) nothing
    here rolls back or drops the tenant database on failure; the error is
    simply raised for the caller to retry.
    """
    tenant = master_db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
    if not tenant:
        raise OnboardingNotFoundError()

    company_data = update.company.model_dump(exclude_unset=True) if update.company is not None else {}
    if company_data:
        for field, value in company_data.items():
            setattr(tenant, _UPDATE_FIELD_MAP.get(field, field), value)
        master_db.commit()
        master_db.refresh(tenant)

    if tenant.tenant_db_name and any(getattr(update, f) is not None for f in _UPDATE_STEP_FIELDS):
        user_id = _safe_uuid(updated_by_user_id)
        tenant_db = tenant_db_manager.get_session(tenant.tenant_db_name, settings.DATABASE_URL)
        try:
            if update.branches is not None:
                _upsert_branches(tenant_db, tenant_id, update.branches, user_id)
            if update.departments is not None:
                _upsert_departments(tenant_db, tenant_id, update.departments, user_id)
            if update.divisions is not None:
                _upsert_divisions(tenant_db, tenant_id, update.divisions, user_id)
            if update.job_codes is not None:
                _upsert_job_codes(tenant_db, tenant_id, update.job_codes, user_id)

            role_translation: Dict[UUID, UUID] = {}
            if update.roles is not None:
                _sync_role_permission_catalog(master_db, tenant_db, update.roles)
                role_translation = _upsert_roles(tenant_db, tenant_id, update.roles)

            if update.users_groups is not None:
                _upsert_user_groups(tenant_db, tenant_id, update.users_groups, role_translation, user_id)
            if update.users is not None:
                _upsert_users(tenant_db, tenant_id, update.users, role_translation)
            if update.subscription is not None:
                _upsert_subscription(tenant_db, tenant_id, update.subscription, user_id)
            if update.security is not None:
                _upsert_security(tenant_db, tenant_id, update.security, user_id)
        except HTTPException:
            tenant_db.rollback()
            raise
        except Exception as exc:
            # Same rationale as create_onboarding's except block — don't let
            # a raw database exception (SQL + bound params) reach the client.
            tenant_db.rollback()
            logger.error(
                "Unexpected error updating tenant %s: %s", tenant_id, exc, exc_info=True
            )
            raise OnboardingUpdateFailedError() from exc
        finally:
            tenant_db.close()

    # Best-effort: keep the tenant DB's copy of the tenants row in sync
    # (only meaningful when company fields actually changed).
    if company_data and tenant.tenant_db_name:
        try:
            tdb = tenant_db_manager.get_session(tenant.tenant_db_name, settings.DATABASE_URL)
            try:
                row = tdb.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
                if row is not None:
                    for col in Tenant.__table__.columns:
                        if col.name != "tenant_id":
                            setattr(row, col.name, getattr(tenant, col.name))
                    tdb.commit()
            finally:
                tdb.close()
        except Exception as exc:
            logger.warning("Onboarding update: tenant DB sync failed for %s: %s", tenant_id, exc)

    master_db.refresh(tenant)
    return tenant, get_onboarding(master_db, tenant_id)


def delete_onboarding(master_db: Session, tenant_id: UUID) -> bool:
    """Soft-delete the client (tenant). The tenant database is left intact."""
    tenant = master_db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
    if not tenant:
        raise OnboardingNotFoundError()
    tenant.is_active = False
    tenant.deleted_at = datetime.now(timezone.utc)
    master_db.commit()
    return True


# ============================================================================
# Drafts — auto-saved when POST /onboarding/ fails partway
# ============================================================================

def save_onboarding_draft(
    master_db: Session,
    draft_id: UUID,
    payload_dict: dict,
    error_message: str,
    created_by: Optional[str] = None,
) -> None:
    """Upsert the submitted payload under draft_id after a failed onboarding attempt.

    Best-effort: never raises — a failure here must not mask the original
    error the caller is already handling.
    """
    try:
        draft = master_db.query(OnboardingDraft).filter(
            OnboardingDraft.draft_id == draft_id
        ).first()
        if draft is None:
            draft = OnboardingDraft(draft_id=draft_id, payload=payload_dict)
            master_db.add(draft)
        else:
            draft.payload = payload_dict
        draft.error_message = error_message
        draft.status = "draft"
        draft.created_by = _safe_uuid(created_by)
        master_db.commit()
    except Exception:
        logger.warning("Failed to save onboarding draft %s", draft_id, exc_info=True)
        master_db.rollback()


def mark_draft_completed(master_db: Session, draft_id: UUID, tenant_id: UUID) -> None:
    """Mark a draft as completed once its draft_id successfully onboards.

    Best-effort — the tenant is already created either way.
    """
    try:
        draft = master_db.query(OnboardingDraft).filter(
            OnboardingDraft.draft_id == draft_id
        ).first()
        if draft is not None:
            draft.status = "completed"
            draft.tenant_id = tenant_id
            master_db.commit()
    except Exception:
        logger.warning("Failed to mark onboarding draft %s completed", draft_id, exc_info=True)
        master_db.rollback()


def _draft_company_fields(payload: Optional[dict]) -> dict:
    """Pull client_name/client_code/contact_email out of a draft's saved
    payload (the company step), so the drafts list can show which client
    each draft belongs to without a separate lookup per row."""
    company = (payload or {}).get("company") or {}
    return {
        "client_name": company.get("client_name"),
        "client_code": company.get("client_code"),
        "contact_email": company.get("contact_email"),
    }


def list_drafts(
    master_db: Session,
    page: int = 1,
    size: int = 10,
    status_filter: Optional[str] = None,
) -> OnboardingDraftListResponse:
    """List saved onboarding drafts, newest first."""
    query = master_db.query(OnboardingDraft)
    if status_filter:
        query = query.filter(OnboardingDraft.status == status_filter)
    total = query.count()
    rows = query.order_by(OnboardingDraft.updated_at.desc()).offset((page - 1) * size).limit(size).all()
    return OnboardingDraftListResponse(
        data=[
            OnboardingDraftSummary(
                draft_id=r.draft_id,
                status=r.status,
                error_message=r.error_message,
                tenant_id=r.tenant_id,
                created_at=r.created_at,
                updated_at=r.updated_at,
                **_draft_company_fields(r.payload),
            )
            for r in rows
        ],
        total=total,
        page=page,
        per_page=size,
    )


def get_draft(master_db: Session, draft_id: UUID) -> OnboardingDraftDetail:
    """Return a saved draft's payload, for resuming the step form."""
    draft = master_db.query(OnboardingDraft).filter(OnboardingDraft.draft_id == draft_id).first()
    if not draft:
        raise OnboardingDraftNotFoundError()
    return OnboardingDraftDetail(
        draft_id=draft.draft_id,
        status=draft.status,
        error_message=draft.error_message,
        tenant_id=draft.tenant_id,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
        payload=draft.payload,
        **_draft_company_fields(draft.payload),
    )


def delete_draft(master_db: Session, draft_id: UUID) -> bool:
    """Discard a saved draft."""
    draft = master_db.query(OnboardingDraft).filter(OnboardingDraft.draft_id == draft_id).first()
    if not draft:
        raise OnboardingDraftNotFoundError()
    master_db.delete(draft)
    master_db.commit()
    return True
