"""
Onboarding API — step-form driven client (tenant) creation.

One POST creates the client and every branch, department, division, job code,
role and user, resolving each record to its parent by array index. GET / PUT /
DELETE manage the onboarded client (company-level).

All endpoints are restricted to master-DB platform users (JWT tenant_id NULL);
tenant users cannot onboard clients.
"""
from typing import Optional
from uuid import UUID
import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_db
from app.core.security import get_current_user
from app.infrastructure.audit_helpers import (
    RISK_SCORE, get_client_ip, get_audit_org_context, get_user_id, get_session_id,
)
from app.infrastructure.audit_tenant import fire_audit_log
from app.infrastructure.tenant_sync_client import sync_tenant_profile
from app.infrastructure.gateway_sync_client import sync_tenant_to_gateway

from app.onboarding.services import onboarding as onboarding_service
from app.onboarding.exceptions import MasterUserRequiredError
from app.onboarding.schemas.onboarding import (
    OnboardingRequest,
    OnboardingCompanyUpdate,
    OnboardingResult,
    OnboardingListResponse,
    OnboardingDetail,
    OnboardingSummary,
    OnboardingDraftListResponse,
    OnboardingDraftDetail,
    OnboardingProgress,
    OnboardingDraftSaveResult,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def require_master_user(current_user=Depends(get_current_user)):
    """Only master-DB platform users (JWT tenant_id NULL) may onboard clients."""
    tenant_id = current_user.get("tenant_id") if isinstance(current_user, dict) else None
    if tenant_id is not None:
        raise MasterUserRequiredError()
    return current_user


def _sync_tenant(tenant) -> None:
    """Fire-and-forget profile + gateway sync (keeps portal and Envoy in step)."""
    asyncio.create_task(sync_tenant_profile(
        tenant_id=str(tenant.tenant_id),
        tenant_name=tenant.tenant_name,
        tenant_code=tenant.tenant_code,
        contact_email=tenant.contact_email,
        contact_phone=tenant.contact_phone,
        is_active=bool(tenant.is_active),
    ))
    asyncio.create_task(sync_tenant_to_gateway(
        tenant_id=str(tenant.tenant_id),
        tenant_name=tenant.tenant_name,
        tenant_code=tenant.tenant_code,
        is_active=bool(tenant.is_active),
    ))


async def _create_and_finalize(
    request: Request,
    payload: OnboardingRequest,
    db: Session,
    current_user,
    draft_id: uuid.UUID,
) -> OnboardingResult:
    """Shared by POST / and POST /drafts (once a draft is complete): create
    the tenant, save a draft on failure (with draft_id attached to the error),
    mark the draft completed on success, fire the audit log + sync, and
    return the OnboardingResult."""
    try:
        tenant, counts, temp_password = onboarding_service.create_onboarding(
            db, payload, created_by_user_id=get_user_id(current_user)
        )
    except Exception as exc:
        detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
        onboarding_service.save_onboarding_draft(
            db,
            draft_id=draft_id,
            payload_dict=payload.model_dump(mode="json"),
            error_message=str(detail),
            created_by=get_user_id(current_user),
        )
        if isinstance(exc, HTTPException):
            raise HTTPException(
                status_code=exc.status_code,
                detail={"message": detail, "draft_id": str(draft_id), "draft_saved": True},
            )
        raise

    onboarding_service.mark_draft_completed(db, draft_id, tenant.tenant_id)

    try:
        tenant_id_audit, entity_id = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="CREATE",
            object_type="Onboarding",
            object_id=str(tenant.tenant_id),
            user_id=get_user_id(current_user),
            tenant_id=tenant_id_audit,
            entity_id=entity_id,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score=RISK_SCORE["CREATE"],
            new_values={
                "tenant_name": tenant.tenant_name,
                "contact_email": tenant.contact_email,
                "counts": counts.model_dump(),
            },
        )
    except Exception:
        pass

    _sync_tenant(tenant)

    return OnboardingResult(
        tenant_id=tenant.tenant_id,
        tenant_db_name=tenant.tenant_db_name,
        owner_email=payload.company.owner_email,
        temp_password=temp_password,
        counts=counts,
    )


@router.post(
    "/",
    response_model=OnboardingResult,
    status_code=status.HTTP_201_CREATED,
    summary="Onboard a client",
    description=(
        "Creates the client (tenant) + its dedicated database, then creates every "
        "branch, department, division, job code, role, user, the subscription and "
        "the security settings in one sequence. Children reference parents by "
        "0-based array index (see the schema). Master-DB users only."
    ),
)
async def onboard_client(
    request: Request,
    payload: OnboardingRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_master_user),
):
    # draft_id is not part of the request — generated here so a failed
    # attempt can still be saved (see save_onboarding_draft below). Since
    # it's server-generated, the caller can't resume by re-sending a known
    # id; they'd look it up via GET /onboarding/drafts.
    draft_id = uuid.uuid4()
    return await _create_and_finalize(request, payload, db, current_user, draft_id)


@router.get(
    "/",
    response_model=OnboardingListResponse,
    summary="List onboarded clients",
    description="Paginated list of onboarded clients (tenants). Master-DB users only.",
)
async def list_clients(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None, description="Filter by client name"),
    db: Session = Depends(get_db),
    current_user=Depends(require_master_user),
):
    return onboarding_service.list_onboardings(db, page=page, size=size, search=search)


# ============================================================================
# Drafts — registered before /{tenant_id} so "drafts" is matched literally
# ============================================================================

@router.post(
    "/drafts",
    response_model=OnboardingDraftSaveResult,
    summary="Save onboarding progress",
    description=(
        "Call this repeatedly as the step form progresses, resending the "
        "accumulated payload each time — pass back ?draft_id=... from a "
        "previous 'draft' response to keep updating the same draft (omit it "
        "on the first save). While company/branches/departments/divisions/"
        "job_codes/roles/users_groups/users don't all have data yet, the "
        "payload is just saved to onboarding_drafts (status 'draft', no "
        "tenant created). Once all 8 are present — subscription/security "
        "stay optional and never block this — the real tenant is created "
        "immediately instead (status 'created'), exactly like POST "
        "/onboarding/. Master-DB users only."
    ),
)
async def save_onboarding_progress(
    request: Request,
    payload: OnboardingRequest,
    draft_id: Optional[UUID] = Query(
        None, description="From a previous 'draft' response, to keep updating the same draft"
    ),
    db: Session = Depends(get_db),
    current_user=Depends(require_master_user),
):
    effective_draft_id = draft_id or uuid.uuid4()
    progress = onboarding_service.compute_payload_progress(payload)

    if not onboarding_service.is_progress_complete(progress):
        onboarding_service.save_onboarding_draft(
            db,
            draft_id=effective_draft_id,
            payload_dict=payload.model_dump(mode="json"),
            error_message=None,
            created_by=get_user_id(current_user),
        )
        return OnboardingDraftSaveResult(status="draft", draft_id=effective_draft_id, progress=progress)

    result = await _create_and_finalize(request, payload, db, current_user, effective_draft_id)
    return OnboardingDraftSaveResult(status="created", result=result)


@router.get(
    "/drafts",
    response_model=OnboardingDraftListResponse,
    summary="List saved onboarding drafts",
    description=(
        "Paginated list of saved onboarding drafts — either from a failed "
        "attempt (see POST /onboarding/) or in-progress saves that don't yet "
        "have all required steps (see POST /onboarding/drafts). Master-DB "
        "users only."
    ),
)
async def list_drafts(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status", description="'draft' or 'completed'"),
    db: Session = Depends(get_db),
    current_user=Depends(require_master_user),
):
    return onboarding_service.list_drafts(db, page=page, size=size, status_filter=status_filter)


@router.get(
    "/drafts/{draft_id}",
    response_model=OnboardingDraftDetail,
    summary="Get a saved onboarding draft",
    description="The saved payload for a failed onboarding attempt, to resume the step form.",
)
async def get_draft(
    draft_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_master_user),
):
    return onboarding_service.get_draft(db, draft_id)


@router.delete(
    "/drafts/{draft_id}",
    summary="Discard a saved onboarding draft",
)
async def delete_draft(
    draft_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_master_user),
):
    onboarding_service.delete_draft(db, draft_id)
    return {"message": "Draft deleted successfully"}


@router.get(
    "/{tenant_id}",
    response_model=OnboardingDetail,
    summary="Get an onboarded client",
    description=(
        "The client (tenant) plus a summary of everything created in its tenant "
        "database: branches, departments, divisions, job codes, roles and users."
    ),
)
async def get_client(
    tenant_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_master_user),
):
    return onboarding_service.get_onboarding(db, tenant_id)


@router.get(
    "/{tenant_id}/progress",
    response_model=OnboardingProgress,
    summary="Onboarding step progress",
    description=(
        "Which of the 10 onboarding steps (company, branches, departments, "
        "divisions, job codes, roles, user groups, users, subscription, security) "
        "already have data, and which to continue with next — powers a 'resume "
        "onboarding' wizard."
    ),
)
async def get_client_progress(
    tenant_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_master_user),
):
    return onboarding_service.get_onboarding_progress(db, tenant_id)


@router.put(
    "/{tenant_id}",
    response_model=OnboardingSummary,
    summary="Update an onboarded client (company fields)",
    description=(
        "Updates the client/company (tenant) fields only. Branches, departments, "
        "divisions, job codes, roles and users are edited via their own module "
        "endpoints."
    ),
)
async def update_client(
    request: Request,
    tenant_id: UUID,
    payload: OnboardingCompanyUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_master_user),
):
    before = payload.model_dump(exclude_unset=True)
    tenant = onboarding_service.update_onboarding(db, tenant_id, payload)

    try:
        tenant_id_audit, entity_id = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="UPDATE",
            object_type="Onboarding",
            object_id=str(tenant_id),
            user_id=get_user_id(current_user),
            tenant_id=tenant_id_audit,
            entity_id=entity_id,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score=RISK_SCORE["UPDATE"],
            new_values=before,
        )
    except Exception:
        pass

    _sync_tenant(tenant)
    return OnboardingSummary.model_validate(tenant)


@router.delete(
    "/{tenant_id}",
    summary="Soft-delete an onboarded client",
    description="Deactivates the client (tenant). The tenant database is left intact.",
)
async def delete_client(
    request: Request,
    tenant_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_master_user),
):
    onboarding_service.delete_onboarding(db, tenant_id)

    try:
        tenant_id_audit, entity_id = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="DELETE",
            object_type="Onboarding",
            object_id=str(tenant_id),
            user_id=get_user_id(current_user),
            tenant_id=tenant_id_audit,
            entity_id=entity_id,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score=RISK_SCORE["DELETE"],
        )
    except Exception:
        pass

    return {"message": "Client deleted successfully"}
