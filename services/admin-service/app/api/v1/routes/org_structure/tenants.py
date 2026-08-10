from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, Request
from sqlalchemy import func
from sqlalchemy.orm import Session
from uuid import UUID
import asyncio
import os
import logging

logger = logging.getLogger(__name__)

from app.infrastructure.database.session import get_db
from app.core.security import get_current_user, get_password_hash, generate_temp_password  # Uses optional auth support
from app.core.config import settings
from app.infrastructure.database.tenant_db_manager import tenant_db_manager
from app.infrastructure.audit_helpers import RISK_SCORE, get_client_ip, get_audit_org_context, get_user_id, get_session_id
from app.infrastructure.audit_tenant import fire_audit_log
from app.infrastructure.tenant_sync_client import sync_tenant_profile
from app.infrastructure.gateway_sync_client import sync_tenant_to_gateway
from app.infrastructure.email_tenant import send_tenant_invitation_email
from app.tenants.models.tenants import Tenant
from app.tenants.schemas.tenants import (
    TenantCreate,
    TenantUpdate,
    TenantResponse,
    TenantCreateResponse,
    TenantListResponse,
    TenantConfigurationStatus
)

# Check if authentication is required
REQUIRE_AUTH = os.getenv("REQUIRE_AUTH", "false").lower() == "true"


def _seed_tenant_db(tenant_db: Session, tenant, temp_password: str) -> None:
    """
    Seed a newly provisioned tenant DB with:
    1. The tenant's own row (satisfies FK constraints from usersetup_basic.tenant_id)
    2. The first admin user in user_setup + usersetup_basic
    """
    from app.tenants.models.tenants import Tenant as TenantModel
    from app.user_setup.models.user_setup import UserSetup, UserSetupBasic
    from app.core.security import get_password_hash

    # 1. Seed the tenant row so FK on usersetup_basic.tenant_id is satisfied.
    # Copy every column so the tenant DB holds the full tenant profile
    # (address, industry, ...), not just the FK fields.
    tenant_row = TenantModel(**{
        col.name: getattr(tenant, col.name)
        for col in TenantModel.__table__.columns
    })
    tenant_db.add(tenant_row)
    tenant_db.flush()

    # 2. Create parent UserSetup record
    user_setup = UserSetup()
    tenant_db.add(user_setup)
    tenant_db.flush()

    # 3. Derive unique identifiers from tenant info
    code = (tenant.tenant_code or str(tenant.tenant_id)[:8]).upper()
    username = tenant.contact_email.split("@")[0]

    # 4. Seed initial admin user
    # can_change_password=True + is_password_change=False → auth-service
    # forces a password change on first login (the invitation email
    # announces the temp password).
    user_basic = UserSetupBasic(
        user_setup_id=user_setup.id,
        firstname="Tenant",
        lastname="Admin",
        employee_id=f"ADMIN-{code}",
        username=username,
        email=tenant.contact_email,
        password_hash=get_password_hash(temp_password),
        tenant_id=tenant.tenant_id,
        status="active",
        is_password_change=False,
        can_change_password=True,
    )
    tenant_db.add(user_basic)
    tenant_db.commit()
    logger.info("Seeded initial admin user '%s' in tenant DB: %s", username, tenant.tenant_db_name)


# Simple admin check for no-auth mode (User model not in scope)
def require_admin_role(current_user=Depends(get_current_user)):
    """Require admin role (bypassed when REQUIRE_AUTH=false)"""
    if not REQUIRE_AUTH:
        return current_user  # Skip role check in no-auth mode
    # In auth mode, you would check roles here
    return current_user

router = APIRouter()

@router.post("/", response_model=TenantCreateResponse)
async def create_tenant(
    request: Request,
    tenant_data: TenantCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin_role)
):
    """Create a new tenant (master platform users only)"""
    # Tenant DBs may only be created by a master-DB user (JWT tenant_id NULL);
    # tenant users are rejected before anything is written.
    caller_tenant_id = current_user.get("tenant_id") if isinstance(current_user, dict) else None
    if caller_tenant_id is not None:
        raise HTTPException(status_code=403, detail="Only master platform users can create tenants")

    # Check if tenant with same tenant_name already exists
    existing_tenant = db.query(Tenant).filter(Tenant.tenant_name == tenant_data.tenant_name).first()
    if existing_tenant:
        raise HTTPException(status_code=400, detail="Tenant with this name already exists")

    # Check if email already exists
    existing_email = db.query(Tenant).filter(Tenant.contact_email == tenant_data.contact_email).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Tenant email already exists")

    # tenant_db_name (and thus the whole per-tenant database) is derived from
    # tenant_code alone, lowercased — a case-different duplicate code would
    # silently reuse another tenant's database (see TenantDatabaseManager.
    # make_db_name / _slugify), so this must be checked case-insensitively.
    if tenant_data.tenant_code:
        existing_code = db.query(Tenant).filter(
            func.lower(Tenant.tenant_code) == tenant_data.tenant_code.lower()
        ).first()
        if existing_code:
            raise HTTPException(status_code=400, detail="Tenant code already exists")

    # Create new tenant. The owner's password is always server-generated
    # (never accepted from the caller) — hashed into owner_password_hash,
    # and the same value seeds the actual login + gets emailed below.
    tenant_dict = tenant_data.model_dump()
    db_tenant = Tenant(**tenant_dict)
    temp_password = generate_temp_password()
    db_tenant.owner_password_hash = get_password_hash(temp_password)
    # is_active is backend-only (not on any schema) — derived from
    # initial_status, same rule as onboarding's create_onboarding().
    db_tenant.is_active = (tenant_data.initial_status or "Active").strip().lower() == "active"
    _creator_id = get_user_id(current_user)
    try:
        db_tenant.created_by = UUID(str(_creator_id)) if _creator_id else None
    except (ValueError, TypeError):
        db_tenant.created_by = None

    # tenant_db_name is a computed property derived from tenant_code — nothing to
    # assign here.
    db.add(db_tenant)
    db.commit()
    db.refresh(db_tenant)

    # Provision the tenant's dedicated PostgreSQL database (CREATE DB + schema).
    # Pass table_permission so only the allowed tables (+ their FK deps) are
    # created — but always include the tables the login/seeding flow needs.
    table_permission = db_tenant.table_permission or None
    if table_permission:
        table_permission = list({*table_permission, "tenants", "user_setup", "usersetup_basic", "audit_logs"})
    ok = tenant_db_manager.provision(
        db_tenant.tenant_db_name,
        settings.DATABASE_URL,
        table_permission,
    )
    if not ok:
        logger.warning(
            "Tenant %s saved but database provisioning failed for %s",
            db_tenant.tenant_id, db_tenant.tenant_db_name
        )

    # Seed the initial admin user into the tenant DB with the generated
    # temp_password (also emailed as the temporary login credential below).
    if ok:
        tenant_db = tenant_db_manager.get_session(db_tenant.tenant_db_name, settings.DATABASE_URL)
        try:
            _seed_tenant_db(tenant_db, db_tenant, temp_password)
            # Invite the tenant by email with a login link (fire-and-forget)
            asyncio.create_task(send_tenant_invitation_email(
                to_email=db_tenant.contact_email,
                tenant_name=db_tenant.tenant_name,
                tenant_id=str(db_tenant.tenant_id),
                temp_password=temp_password,
                # Login link points at the tenant's own frontend (first allowed origin)
                tenant_app_url=(db_tenant.allowed_origins[0] if db_tenant.allowed_origins else None),
            ))
        except Exception as seed_exc:
            logger.warning(
                "Tenant %s provisioned but user seeding failed: %s",
                db_tenant.tenant_id, seed_exc
            )
        finally:
            tenant_db.close()

    # Audit log: tenant created
    try:
        tenant_id_audit, entity_id = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="CREATE",
            object_type="Tenant",
            object_id=str(db_tenant.tenant_id),
            user_id=get_user_id(current_user),
            tenant_id=tenant_id_audit,
            entity_id=entity_id,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score=RISK_SCORE["CREATE"],
            new_values={
                "tenant_name": db_tenant.tenant_name,
                "contact_email": db_tenant.contact_email,
            },
        )
    except Exception:
        pass

    # Sync to tenant portal (non-blocking background task)
    asyncio.create_task(sync_tenant_profile(
        tenant_id=str(db_tenant.tenant_id),
        tenant_name=db_tenant.tenant_name,
        tenant_code=db_tenant.tenant_code,
        contact_email=db_tenant.contact_email,
        contact_phone=db_tenant.contact_phone,
        is_active=bool(db_tenant.is_active),
    ))
    # Sync to API gateway so Envoy routing stays in sync (non-blocking)
    asyncio.create_task(sync_tenant_to_gateway(
        tenant_id=str(db_tenant.tenant_id),
        tenant_name=db_tenant.tenant_name,
        tenant_code=db_tenant.tenant_code,
        is_active=bool(db_tenant.is_active),
    ))

    tenant_dict = TenantResponse.model_validate(db_tenant).model_dump()
    tenant_dict["temp_password"] = temp_password
    return tenant_dict

@router.get("/", response_model=TenantListResponse)
async def list_tenants(
    request: Request,
    response: Response,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    initial_status: Optional[str] = Query(None),
    _t: Optional[str] = Query(None),  # Cache-busting parameter (ignored)
    db: Session = Depends(get_db),
    current_user=Depends(require_admin_role)
):
    """List all tenants with pagination and filtering (admin only)"""
    # Add cache control headers to prevent browser caching
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    query = db.query(Tenant)

    # Apply filters
    if search:
        query = query.filter(Tenant.tenant_name.ilike(f"%{search}%"))

    # Get total count
    total = query.count()

    # Apply FILO sorting (newest first) before pagination
    query = query.order_by(Tenant.created_at.desc())

    # Apply pagination
    tenants = query.offset((page - 1) * size).limit(size).all()

    result = TenantListResponse(
        tenants=tenants,
        total=total,
        page=page,
        page_size=size,
        total_pages=(total + size - 1) // size
    )
    try:
        tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="READ",
            object_type="Tenant",
            user_id=get_user_id(current_user),
            tenant_id=tenant_id_audit,
            entity_id=entity_id_audit,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score="LOW",
        )
    except Exception:
        pass
    return result

@router.put("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    request: Request,
    tenant_id: UUID,
    tenant_data: TenantUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin_role)
):
    """Update tenant (admin only)"""
    tenant = db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Capture old values before update for audit
    old_values = {
        "tenant_name": tenant.tenant_name,
        "contact_email": tenant.contact_email,
    }

    # Update fields
    update_data = tenant_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tenant, field, value)

    db.commit()
    db.refresh(tenant)

    # Audit log: tenant updated
    try:
        tenant_id_audit, entity_id = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="UPDATE",
            object_type="Tenant",
            object_id=str(tenant_id),
            user_id=get_user_id(current_user),
            tenant_id=tenant_id_audit,
            entity_id=entity_id,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score=RISK_SCORE["UPDATE"],
            old_values=old_values,
            new_values=update_data,
        )
    except Exception:
        pass

    # Sync updated data to tenant portal (non-blocking background task)
    asyncio.create_task(sync_tenant_profile(
        tenant_id=str(tenant.tenant_id),
        tenant_name=tenant.tenant_name,
        tenant_code=tenant.tenant_code,
        contact_email=tenant.contact_email,
        contact_phone=tenant.contact_phone,
        is_active=bool(tenant.is_active),
    ))
    # Sync updated data to API gateway so Envoy routing stays in sync (non-blocking)
    asyncio.create_task(sync_tenant_to_gateway(
        tenant_id=str(tenant.tenant_id),
        tenant_name=tenant.tenant_name,
        tenant_code=tenant.tenant_code,
        is_active=bool(tenant.is_active),
    ))

    return tenant

@router.delete("/{tenant_id}")
async def delete_tenant(
    request: Request,
    tenant_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin_role)
):
    """Soft delete tenant (admin only)"""
    tenant = db.query(Tenant).filter(
        Tenant.tenant_id == tenant_id,
        Tenant.is_active == True
    ).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Snapshot name before soft delete for audit
    old_tenant_name = tenant.tenant_name

    # Perform soft delete
    tenant.is_active = False

    db.commit()

    # Audit log: tenant deleted
    try:
        tenant_id_audit, entity_id = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="DELETE",
            object_type="Tenant",
            object_id=str(tenant_id),
            user_id=get_user_id(current_user),
            tenant_id=tenant_id_audit,
            entity_id=entity_id,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score=RISK_SCORE["DELETE"],
            old_values={"name": old_tenant_name},
        )
    except Exception:
        pass

    # Sync deactivation to tenant portal
    asyncio.create_task(sync_tenant_profile(
        tenant_id=str(tenant.tenant_id),
        tenant_name=tenant.tenant_name,
        tenant_code=tenant.tenant_code,
        contact_email=tenant.contact_email,
        contact_phone=tenant.contact_phone,
        is_active=False,
    ))
    # Sync deactivation to API gateway so Envoy routing stays in sync
    asyncio.create_task(sync_tenant_to_gateway(
        tenant_id=str(tenant.tenant_id),
        tenant_name=tenant.tenant_name,
        tenant_code=tenant.tenant_code,
        is_active=False,
    ))

    return {"message": "Tenant deleted successfully"}
