"""
Onboarding API — step-form driven client (tenant) creation.

POST / is called repeatedly as the step form progresses. Each call only
needs to include the step(s) being added or changed THIS time (pass back
?draft_id=... from a previous 'draft' response after the first call) — the
server merges those step(s) onto whatever was saved under that draft_id
earlier, so already-completed steps don't need to be resent.

?finalize=true|false (default false) controls whether the call may actually
provision:
  - finalize=false — the merged payload is always just saved to
    onboarding_drafts (status 'draft', HTTP 200, no tenant created), even
    once every step happens to have data.
  - finalize=true — the merged payload is strictly validated; if every one
    of the 10 steps (matching the wizard's own step list, nothing optional)
    is present and valid, the real tenant + its dedicated database is
    created (status 'created', HTTP 201). Otherwise HTTP 422 listing which
    step(s) are still missing.

GET / PUT / DELETE manage the onboarded client (company-level).

All endpoints are restricted to master-DB platform users (JWT tenant_id NULL);
tenant users cannot onboard clients.
"""
from typing import Optional
from uuid import UUID
import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_db
from app.core.security import get_current_user
from app.infrastructure.audit_helpers import (
    RISK_SCORE, get_client_ip, get_audit_org_context, get_user_id, get_session_id,
)
from app.infrastructure.audit_tenant import fire_audit_log
from app.infrastructure.tenant_sync_client import sync_tenant_profile
from app.infrastructure.gateway_sync_client import sync_tenant_to_gateway
from app.infrastructure.email_tenant import (
    send_tenant_invitation_email,
    send_user_invite_email,
)

from app.onboarding.services import onboarding as onboarding_service
from app.onboarding.exceptions import MasterUserRequiredError, OnboardingDetailFailedError
from app.onboarding.schemas.onboarding import (
    OnboardingRequest,
    OnboardingStepRequest,
    OnboardingUpdate,
    OnboardingResult,
    OnboardingListResponse,
    OnboardingDetail,
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


def _send_onboarding_emails(tenant, payload: OnboardingRequest, temp_password: str) -> None:
    """Fire-and-forget: owner welcome (credentials), and per-user invites
    (with each user's own step-form password) for users[] entries with
    send_invite_email true. contact_email is not emailed - it's stored on
    the tenant for reference only."""
    # tenants.deployed_url is the login link's source of truth (falls back to
    # settings.FRONTEND_LOGIN_URL inside email_tenant.py when unset).
    # allowed_origins is a separate concept (usersetup_basic.allowed_origins —
    # the master-DB user's own post-login redirect target) and isn't used here.
    tenant_app_url = tenant.deployed_url

    asyncio.create_task(send_tenant_invitation_email(
        to_email=payload.company.owner_email,
        tenant_name=tenant.tenant_name,
        tenant_id=str(tenant.tenant_id),
        temp_password=temp_password,
        tenant_app_url=tenant_app_url,
    ))

    for u in payload.users:
        if u.send_invite_email:
            asyncio.create_task(send_user_invite_email(
                to_email=u.email,
                first_name=u.first_name,
                tenant_name=tenant.tenant_name,
                tenant_id=str(tenant.tenant_id),
                tenant_app_url=tenant_app_url,
                password=u.password,
            ))


async def _create_and_finalize(
    request: Request,
    payload: OnboardingRequest,
    db: Session,
    current_user,
    draft_id: uuid.UUID,
) -> OnboardingResult:
    """Called once POST /'s payload is complete: create the tenant, save a
    draft on failure (with draft_id attached to the error), mark the draft
    completed on success, fire the audit log + sync, and return the
    OnboardingResult."""
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
    _send_onboarding_emails(tenant, payload, temp_password)

    # Full detail — same query GET /{tenant_id} runs — so the creation
    # response carries every record actually written (company, branches,
    # ... subscription, security), not just counts. The tenant is already
    # committed at this point; if building the full detail throws for any
    # reason, fall back to the minimal-but-valid result built straight from
    # what create_onboarding() already returned, instead of losing tenant_id/
    # temp_password behind an opaque 500 for a tenant that really was created.
    try:
        detail = onboarding_service.get_onboarding(db, tenant.tenant_id)
        return OnboardingResult(**detail.model_dump(), temp_password=temp_password)
    except Exception:
        logger.error(
            "Tenant %s was created but building its full detail response failed; "
            "falling back to the minimal result.", tenant.tenant_id, exc_info=True,
        )
        return OnboardingResult(
            tenant_id=tenant.tenant_id,
            company=payload.company,
            is_active=tenant.is_active,
            tenant_db_name=tenant.tenant_db_name,
            counts=counts,
            temp_password=temp_password,
        )


@router.post(
    "/",
    response_model=OnboardingDraftSaveResult,
    status_code=status.HTTP_201_CREATED,
    summary="Onboard a client",
    description=(
        "Call this repeatedly as the step form progresses — each call only "
        "needs to include the step(s) being added or changed THIS time (pass "
        "back ?draft_id=... from a previous 'draft' response to keep updating "
        "the same draft; omit it on the first call). The server merges "
        "whichever step(s) you send onto whatever was saved under that "
        "draft_id earlier, so already-completed steps don't need to be "
        "resent — e.g. once company/branches/departments/divisions are saved, "
        "a later call can send just job_codes/roles/users_groups/users/"
        "subscription/security. Note this merge is step-level, not item-"
        "level: resending a step's array replaces the previously saved array "
        "for that step outright, so a single step's items must all be sent "
        "together.\n\n"
        "?finalize=true|false (default false) controls whether this call may "
        "actually provision:\n"
        "- finalize=false — the merged payload is always just saved to "
        "onboarding_drafts (status 'draft', HTTP 200), so it can be resumed "
        "later via GET /onboarding/drafts/{draft_id}. Never provisions, even "
        "when all 10 steps happen to be present already.\n"
        "- finalize=true — the merged payload is strictly validated and, if "
        "every one of the 10 steps (matching the wizard's own step list, "
        "nothing optional) is present and valid, the client (tenant) + its "
        "dedicated database is created (status 'created', HTTP 201): every "
        "branch, department, division, job code, role, user, the "
        "subscription and the security settings in one sequence. Otherwise "
        "422, listing which step(s) are still missing (and the payload is "
        "still saved as a draft, resumable the same way).\n\n"
        "Children reference parents by the client-supplied UUIDs carried in "
        "the payload (see the schema). Master-DB users only."
    ),
)
async def onboard_client(
    request: Request,
    response: Response,
    payload: OnboardingStepRequest,
    draft_id: Optional[UUID] = Query(
        None, description="From a previous 'draft' response, to keep updating the same draft"
    ),
    finalize: bool = Query(
        False,
        description=(
            "False (default): always saved as a draft — 200 status:'draft'. Never "
            "provisions, even when all 10 steps are present. True: validate + "
            "provision — 201 status:'created' when all 10 steps are present and "
            "valid, 422 listing which steps are missing otherwise."
        ),
    ),
    db: Session = Depends(get_db),
    current_user=Depends(require_master_user),
):
    # draft_id is generated here on the first call so a not-yet-complete or
    # failed attempt can still be saved (see save_onboarding_draft below);
    # pass it back on later calls to keep updating (merging onto) the same
    # draft instead of creating a new one.
    effective_draft_id = draft_id or uuid.uuid4()

    # Only the fields THIS call actually included (exclude_unset) are merged
    # onto the previously saved draft — an omitted field keeps its earlier
    # saved value instead of being wiped out.
    incoming = payload.model_dump(exclude_unset=True, mode="json")
    merged = onboarding_service.merge_onboarding_payload(db, effective_draft_id, incoming)
    progress = onboarding_service.compute_dict_progress(merged)

    if not finalize:
        # finalize=false (the default): always just save the draft, even if
        # every step happens to already be present — the caller must pass
        # finalize=true to actually provision.
        onboarding_service.save_onboarding_draft(
            db,
            draft_id=effective_draft_id,
            payload_dict=merged,
            error_message=None,
            created_by=get_user_id(current_user),
        )
        response.status_code = status.HTTP_200_OK
        return OnboardingDraftSaveResult(status="draft", draft_id=effective_draft_id, progress=progress)

    if not onboarding_service.is_progress_complete(progress):
        missing_steps = [s.step for s in progress.steps if not s.completed]
        detail_msg = f"Missing required step(s): {', '.join(missing_steps)}"
        onboarding_service.save_onboarding_draft(
            db,
            draft_id=effective_draft_id,
            payload_dict=merged,
            error_message=detail_msg,
            created_by=get_user_id(current_user),
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": detail_msg,
                "missing_steps": missing_steps,
                "draft_id": str(effective_draft_id),
                "draft_saved": True,
            },
        )

    # All 10 steps are present in the merged payload — now strictly
    # re-validate it as a full OnboardingRequest (a step merged in on an
    # earlier call may still be incomplete on its own, e.g. a job_code
    # missing division_id) before actually creating anything.
    try:
        full_payload = OnboardingRequest(**merged)
    except ValidationError as exc:
        detail_msg = str(exc)
        onboarding_service.save_onboarding_draft(
            db,
            draft_id=effective_draft_id,
            payload_dict=merged,
            error_message=detail_msg,
            created_by=get_user_id(current_user),
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": detail_msg, "draft_id": str(effective_draft_id), "draft_saved": True},
        )

    result = await _create_and_finalize(request, full_payload, db, current_user, effective_draft_id)
    return OnboardingDraftSaveResult(status="created", result=result)


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

@router.get(
    "/drafts",
    response_model=OnboardingDraftListResponse,
    summary="List saved onboarding drafts",
    description=(
        "Paginated list of saved onboarding drafts — step-form submissions "
        "that don't yet have all 10 required steps, saved automatically by "
        "POST /onboarding/. Master-DB users only."
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
    try:
        return onboarding_service.get_onboarding(db, tenant_id)
    except HTTPException:
        raise
    except Exception:
        # Never let an unexpected serialization error propagate unhandled —
        # that surfaces to the caller as an empty-bodied 500 with nothing to
        # go on. Log the full traceback server-side and return a clean error
        # instead (same rationale as OnboardingCreationFailedError).
        logger.error(
            "Failed to build detail for tenant %s", tenant_id, exc_info=True,
        )
        raise OnboardingDetailFailedError()


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
    response_model=OnboardingDetail,
    summary="Update an onboarded client",
    description=(
        "Updates company/tenant fields and/or upserts any of the other 9 "
        "onboarding steps (branches, departments, divisions, job codes, "
        "roles, user groups, users, subscription, security) against the "
        "tenant's own database — same shape as OnboardingRequest, but every "
        "field is optional and independent: a step left out of the request "
        "is left untouched. Within a step that IS included, each item is "
        "upserted by the same id that step already carries (branches by "
        "entity_id, ... roles by role_code, users by email — see "
        "OnboardingUpdate's docstring) — an unmatched id creates a new "
        "record, a matching id updates it in place, nothing already in the "
        "tenant DB is ever deleted by this endpoint. Returns the same shape "
        "as GET /{tenant_id}."
    ),
)
async def update_client(
    request: Request,
    tenant_id: UUID,
    payload: OnboardingUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_master_user),
):
    before = payload.model_dump(exclude_unset=True)
    # users[].password (if the users step was included) is plaintext in the
    # request — never let it land in the audit log.
    if before.get("users"):
        before["users"] = [{**u, "password": "***"} for u in before["users"]]

    try:
        tenant, detail = onboarding_service.update_onboarding(
            db, tenant_id, payload, updated_by_user_id=get_user_id(current_user)
        )
    except HTTPException:
        raise
    except Exception:
        # update_onboarding() applies every upsert and commits, then builds
        # its return value via the same get_onboarding() detail-serialization
        # path GET uses — a failure there must not surface as an empty-bodied
        # 500 (the mutations already succeeded).
        logger.error(
            "Client %s was updated but building its detail response failed",
            tenant_id, exc_info=True,
        )
        raise OnboardingDetailFailedError()

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
    return detail


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
