"""
Onboarding service — creates a client (tenant) and its entire org structure in
one sequence.

Flow (POST):
  1. Create the tenant row in the MASTER db and provision its dedicated DB.
  2. In the TENANT db: seed the tenant row (so FKs / get_tenant resolve) and the
     owner admin user, then create branches -> departments -> divisions ->
     job codes -> roles -> users, resolving each child to its parent by the
     0-based array index carried in the payload.

Reuse: branches/departments/divisions/job codes go through the existing per-record
services (validation, locale derivation, audit). Roles and users are written
directly (they only need the small subset the step form collects).

Atomicity: the per-record services commit as they go, so this is NOT a single
transaction. On failure after the tenant is created, the tenant is marked
onboarding_status='failed' and the error is surfaced; the (empty/partial) client
can be retried or deleted.
"""
import logging
from typing import List, Optional, Tuple
from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash
from app.infrastructure.database.tenant_db_manager import tenant_db_manager

from app.tenants.models.tenants import Tenant

from app.entities.models.entity import Entity
from app.entities.services.entity import create_entity
from app.entities.schemas.entity import EntityCreate
from app.departments.models.departments import Department
from app.departments.services.departments import create_department
from app.departments.schemas.departments import DepartmentCreate
from app.divisions.models.divisions import Division
from app.divisions.services.divisions import create_division
from app.divisions.schemas.divisions import DivisionCreate
from app.job_codes.models.job_codes import JobCode
from app.job_codes.services.job_codes import create_job_code
from app.job_codes.schemas.job_codes import (
    JobCodeCreate,
    JobCodeBasicInfoCreate,
    JobCodeSkillsCreate,
)
from app.user_role.models.user_role import UserRoleMain, UserRoleBasic
from app.user_setup.models.user_setup import UserSetup, UserSetupBasic
from app.subscription.models.subscription import Subscription
from app.subscription.services.subscription import create_subscription
from app.security.models.security import Security
from app.security.services.security import create_security

from app.onboarding.schemas.onboarding import (
    OnboardingRequest,
    OnboardingCompanyUpdate,
    OnboardingCounts,
    OnboardingDetail,
    OnboardingSummary,
    OnboardingListResponse,
    _NamedRef,
)
from app.onboarding.exceptions import (
    DuplicateTenantError,
    OnboardingUnknownReferenceError,
    OnboardingDuplicateError,
    TenantProvisioningError,
    OnboardingNotFoundError,
)

logger = logging.getLogger(__name__)


def _safe_uuid(value) -> Optional[UUID]:
    try:
        return UUID(str(value)) if value else None
    except (ValueError, TypeError):
        return None


def _validate_indices(payload: OnboardingRequest) -> None:
    """Fail fast (422) if any child references an unknown parent UUID.

    Every created record carries a client-supplied UUID (branches[].entity_id,
    departments[].department_id, divisions[].id, roles[].id). Those ids must be
    unique within each list, and every reference must point at one of them —
    both are validated here by set membership.
    """
    branch_ids = [b.entity_id for b in payload.branches]
    branch_id_set = set(branch_ids)
    if len(branch_id_set) != len(branch_ids):
        raise OnboardingDuplicateError("branches[].entity_id")

    department_ids = [d.department_id for d in payload.departments]
    department_id_set = set(department_ids)
    if len(department_id_set) != len(department_ids):
        raise OnboardingDuplicateError("departments[].department_id")

    division_ids = [dv.id for dv in payload.divisions]
    division_id_set = set(division_ids)
    if len(division_id_set) != len(division_ids):
        raise OnboardingDuplicateError("divisions[].id")

    role_ids = [r.id for r in payload.roles]
    role_id_set = set(role_ids)
    if len(role_id_set) != len(role_ids):
        raise OnboardingDuplicateError("roles[].id")

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
        if r.parent_role_id is not None and r.parent_role_id not in role_id_set:
            raise OnboardingUnknownReferenceError(f"roles[{i}]", r.parent_role_id, "roles")
    for i, u in enumerate(payload.users):
        if u.role_id is not None and u.role_id not in role_id_set:
            raise OnboardingUnknownReferenceError(f"users[{i}]", u.role_id, "roles")
        if u.entity_id is not None and u.entity_id not in branch_id_set:
            raise OnboardingUnknownReferenceError(f"users[{i}]", u.entity_id, "branches")


def _split_full_name(full_name: Optional[str]) -> Tuple[str, str]:
    """Split 'Owner full name' into (first, last); defaults to Account / Owner."""
    parts = (full_name or "").strip().split()
    if not parts:
        return "Account", "Owner"
    if len(parts) == 1:
        return parts[0], parts[0]
    return parts[0], " ".join(parts[1:])


def _seed_tenant_row(tenant_db: Session, tenant: Tenant) -> None:
    """Copy the full tenant profile into the tenant DB (satisfies FKs / get_tenant)."""
    tenant_db.add(Tenant(**{
        col.name: getattr(tenant, col.name) for col in Tenant.__table__.columns
    }))
    tenant_db.commit()


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
    status: str = "active",
    role_id: Optional[UUID] = None,
    entity_id: Optional[UUID] = None,
    user_group_id: Optional[UUID] = None,
    send_invite_email: bool = False,
) -> Tuple[UUID, UUID]:
    """Create user_setup + usersetup_basic (+ optional role/entity assignment)."""
    user_setup = UserSetup()
    tenant_db.add(user_setup)
    tenant_db.flush()

    basic = UserSetupBasic(
        user_setup_id=user_setup.id,
        firstname=firstname,
        lastname=lastname,
        employee_id=employee_id,
        username=username,
        email=email,
        password_hash=get_password_hash(password),
        phone_number=phone,
        status=status or "active",
        tenant_id=tenant_id,
        entities=[entity_id] if entity_id else None,
        default_entity=entity_id,
        role_id=role_id,
        user_group_id=user_group_id,
        send_invite_email=send_invite_email,
        is_password_change=False,
        can_change_password=True,
    )
    tenant_db.add(basic)
    tenant_db.commit()
    return user_setup.id, basic.id


def _mark_status(master_db: Session, tenant: Tenant, status: str) -> None:
    try:
        tenant.onboarding_status = status
        master_db.commit()
    except Exception:
        master_db.rollback()


def create_onboarding(
    master_db: Session,
    payload: OnboardingRequest,
    created_by_user_id: Optional[str] = None,
) -> Tuple[Tenant, OnboardingCounts]:
    """Create the tenant + its whole org structure. Returns (tenant, counts)."""
    company = payload.company

    # Duplicate guard (master DB)
    if master_db.query(Tenant).filter(Tenant.tenant_name == company.client_name).first():
        raise DuplicateTenantError("A client with this name already exists")
    if master_db.query(Tenant).filter(Tenant.contact_email == company.contact_email).first():
        raise DuplicateTenantError("A client with this contact email already exists")

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
        onboarding_status="in_progress",
        is_active=(company.status or "active").strip().lower() == "active",
        created_by=_safe_uuid(created_by_user_id),
    )
    master_db.add(tenant)
    master_db.commit()
    master_db.refresh(tenant)

    # The DB name is derived from tenant_code (Tenant.tenant_db_name is a computed
    # property) — a client code is required to provision the dedicated database.
    if not tenant.tenant_db_name:
        _mark_status(master_db, tenant, "failed")
        raise TenantProvisioningError()

    # 2. Provision the tenant's dedicated database (CREATE DB + all tables)
    ok = tenant_db_manager.provision(tenant.tenant_db_name, settings.DATABASE_URL, None)
    if not ok:
        _mark_status(master_db, tenant, "failed")
        raise TenantProvisioningError(tenant.tenant_db_name)

    tenant_db = tenant_db_manager.get_session(tenant.tenant_db_name, settings.DATABASE_URL)
    counts = OnboardingCounts()
    try:
        tenant_id = tenant.tenant_id

        # Seed the tenant row into the tenant DB
        _seed_tenant_row(tenant_db, tenant)

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
            password=company.owner_password,
            tenant_id=tenant_id,
        )
        counts.users += 1

        # 3. Branches (entities) — created with the client-supplied entity_id so
        #    children can reference them by that UUID.
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
                    # d.entity_id is the branch's client-supplied UUID (validated
                    # to exist among branches) — used directly.
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
                    entity_id=dv.entity_id,
                    # dv.department_id is a department's client-supplied UUID
                    # (validated to exist among departments) — used directly.
                    department_id=dv.department_id,
                    division_head=dv.division_head,
                    hierarchy_level=dv.hierarchy_level,
                    description=dv.description,
                ),
                tenant_id=tenant_id,
                user_id=_safe_uuid(created_by_user_id),
                division_id=dv.id,
            )
            division_ids.append(division.id)
        counts.divisions = len(division_ids)

        # 6. Job codes
        for j in payload.job_codes:
            create_job_code(
                tenant_db,
                JobCodeCreate(
                    job_code=j.job_code,
                    job_title=j.job_title,
                    basic_info=JobCodeBasicInfoCreate(
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
                    ),
                    skills=(
                        JobCodeSkillsCreate(
                            required_skills=j.required_skills,
                            key_responsibilities=j.key_responsibilities,
                        )
                        if (j.required_skills or j.key_responsibilities) else None
                    ),
                ),
                tenant_id=tenant_id,
                user_id=_safe_uuid(created_by_user_id),
            )
        counts.job_codes = len(payload.job_codes)

        # 7. Roles
        role_ids: List[UUID] = []
        admin_role_id: Optional[UUID] = None
        for r in payload.roles:
            # Client supplies the role's UUID (user_role.id) so parent_role_id and
            # users[].role_id can reference it in the same request.
            main = UserRoleMain(id=r.id)
            tenant_db.add(main)
            tenant_db.flush()
            tenant_db.add(UserRoleBasic(
                user_role_id=main.id,
                tenant_id=tenant_id,
                role_name=r.role_name,
                role_code=r.role_code,
                description=r.description,
                role_level=r.role_level,
                parent_role_id=r.parent_role_id,
                access_scope=r.access_scope,
                is_admin=r.is_admin,
                default_for_new_users=r.default_for_new_users,
                active=r.active,
            ))
            role_ids.append(main.id)
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

        # 8. Users
        for u in payload.users:
            _create_user_row(
                tenant_db,
                firstname=u.first_name,
                lastname=u.last_name,
                employee_id=u.employee_id,
                username=u.username,
                email=u.email,
                password=u.password,
                tenant_id=tenant_id,
                phone=u.phone,
                status=u.status or "active",
                role_id=u.role_id,
                entity_id=u.entity_id,
                user_group_id=u.user_group_id,
                send_invite_email=u.send_invite_email,
            )
            counts.users += 1

        # 9. Subscription plan (optional; one per client)
        if payload.subscription is not None:
            create_subscription(
                tenant_db,
                payload.subscription,
                tenant_id=tenant_id,
                user_id=_safe_uuid(created_by_user_id),
            )
            counts.subscription = 1

        # 10. Security settings (optional; one per client)
        if payload.security is not None:
            create_security(
                tenant_db,
                payload.security,
                tenant_id=tenant_id,
                user_id=_safe_uuid(created_by_user_id),
            )
            counts.security = 1

    except Exception:
        tenant_db.rollback()
        _mark_status(master_db, tenant, "failed")
        raise
    finally:
        tenant_db.close()

    _mark_status(master_db, tenant, "completed")
    master_db.refresh(tenant)
    return tenant, counts


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
    """Return the tenant plus a summary of everything in its tenant DB."""
    tenant = master_db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
    if not tenant:
        raise OnboardingNotFoundError()

    counts = OnboardingCounts()
    branches: List[_NamedRef] = []
    departments: List[_NamedRef] = []
    divisions: List[_NamedRef] = []
    job_codes: List[_NamedRef] = []
    roles: List[_NamedRef] = []
    users: List[_NamedRef] = []
    subscription_count = 0
    security_count = 0

    if tenant.tenant_db_name:
        tdb = tenant_db_manager.get_session(tenant.tenant_db_name, settings.DATABASE_URL)
        try:
            branches = [
                _NamedRef(id=e.entity_id, name=e.entity_name, code=e.entity_code)
                for e in tdb.query(Entity).filter(Entity.deleted == False).all()  # noqa: E712
            ]
            departments = [
                _NamedRef(id=d.department_id, name=d.department_name, code=d.department_code)
                for d in tdb.query(Department).filter(Department.is_deleted == False).all()  # noqa: E712
            ]
            divisions = [
                _NamedRef(id=dv.id, name=dv.division_name, code=dv.division_code)
                for dv in tdb.query(Division).filter(Division.deleted_at.is_(None)).all()
            ]
            job_codes = [
                _NamedRef(id=j.id, name=j.job_title, code=j.job_code)
                for j in tdb.query(JobCode).filter(JobCode.deleted_at.is_(None)).all()
            ]
            roles = [
                _NamedRef(id=r.id, name=r.role_name, code=r.role_code)
                for r in tdb.query(UserRoleBasic).all()
            ]
            users = [
                _NamedRef(id=u.id, name=f"{u.firstname} {u.lastname}".strip(), code=u.email)
                for u in tdb.query(UserSetupBasic).all()
            ]
            subscription_count = tdb.query(Subscription).count()
            security_count = tdb.query(Security).count()
        finally:
            tdb.close()

    counts.branches = len(branches)
    counts.departments = len(departments)
    counts.divisions = len(divisions)
    counts.job_codes = len(job_codes)
    counts.roles = len(roles)
    counts.users = len(users)
    counts.subscription = subscription_count
    counts.security = security_count

    return OnboardingDetail(
        tenant_id=tenant.tenant_id,
        client_name=tenant.tenant_name,
        client_code=tenant.tenant_code,
        contact_email=tenant.contact_email,
        onboarding_status=tenant.onboarding_status,
        is_active=tenant.is_active,
        tenant_db_name=tenant.tenant_db_name,
        counts=counts,
        branches=branches,
        departments=departments,
        divisions=divisions,
        job_codes=job_codes,
        roles=roles,
        users=users,
    )


# Map OnboardingCompanyUpdate field -> Tenant column
_UPDATE_FIELD_MAP = {
    "client_name": "tenant_name",
    "client_code": "tenant_code",
}


def update_onboarding(
    master_db: Session,
    tenant_id: UUID,
    update: OnboardingCompanyUpdate,
) -> Tenant:
    """Update the client/company (tenant) fields only, and mirror to the tenant DB."""
    tenant = master_db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
    if not tenant:
        raise OnboardingNotFoundError()

    data = update.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(tenant, _UPDATE_FIELD_MAP.get(field, field), value)
    master_db.commit()
    master_db.refresh(tenant)

    # Best-effort: keep the tenant DB's copy of the tenants row in sync
    if tenant.tenant_db_name:
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

    return tenant


def delete_onboarding(master_db: Session, tenant_id: UUID) -> bool:
    """Soft-delete the client (tenant). The tenant database is left intact."""
    tenant = master_db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
    if not tenant:
        raise OnboardingNotFoundError()
    tenant.is_active = False
    tenant.deleted_at = datetime.now(timezone.utc)
    master_db.commit()
    return True
