"""
Inbound sync endpoint — receives tenant data pushed from clan-tenant-portal-be.

Route:  POST /api/v1/sync/tenants
Auth:   x-internal-key header (service-to-service only, no JWT needed)
"""
import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.infrastructure.database.session import get_db
from app.tenants.models.tenants import Tenant

logger = logging.getLogger(__name__)

router = APIRouter()


# ──────────────────────────────── auth ────────────────────────────────


def _require_internal_key(
    x_internal_key: Optional[str] = Header(None, alias="x-internal-key"),
) -> None:
    if not x_internal_key or x_internal_key != settings.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing or invalid internal API key",
        )


# ──────────────────────────────── schema ──────────────────────────────


class PortalTenantPayload(BaseModel):
    """Data sent by clan-tenant-portal-be when its Tenant record changes."""
    portal_tenant_id: str            # tenant-portal PK (maps to Tenant.gateway_tenant_ref)
    admin_tenant_id: Optional[str] = None  # admin-service PK (for lookup when known)
    name: str
    slug: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    status: str = "active"           # active | suspended | trial | cancelled


# ──────────────────────────────── endpoint ────────────────────────────


@router.post(
    "/tenants",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(_require_internal_key)],
)
def sync_tenant_from_portal(
    payload: PortalTenantPayload,
    db: Session = Depends(get_db),
):
    """
    Receive a tenant update pushed from clan-tenant-portal-be.
    Looks up by admin_tenant_id first, then by gateway_tenant_ref.
    Only updates — never creates (admin-service is the source of truth for tenant creation).
    """
    tenant: Optional[Tenant] = None

    # 1. Prefer explicit admin_tenant_id cross-reference
    if payload.admin_tenant_id:
        try:
            tenant = db.query(Tenant).filter(
                Tenant.tenant_id == uuid.UUID(payload.admin_tenant_id)
            ).first()
        except (ValueError, AttributeError):
            pass

    # 2. Fall back to gateway_tenant_ref
    if not tenant:
        try:
            tenant = db.query(Tenant).filter(
                Tenant.gateway_tenant_ref == uuid.UUID(payload.portal_tenant_id)
            ).first()
        except (ValueError, AttributeError):
            pass

    if not tenant:
        logger.warning(
            "[sync-inbound] tenant not found — portal_id=%s admin_id=%s",
            payload.portal_tenant_id,
            payload.admin_tenant_id,
        )
        return {"status": "not_found", "detail": "No matching tenant in admin-service"}

    # Apply updates
    tenant.tenant_name = payload.name
    if payload.contact_email:
        tenant.contact_email = payload.contact_email
    if payload.contact_phone:
        tenant.contact_phone = payload.contact_phone
    tenant.is_active = payload.status == "active"
    # Always pin the cross-reference
    try:
        tenant.gateway_tenant_ref = uuid.UUID(payload.portal_tenant_id)
    except ValueError:
        pass

    db.commit()
    logger.info("[sync-inbound] updated tenant %s from portal", tenant.tenant_id)

    return {
        "status": "updated",
        "tenant_id": str(tenant.tenant_id),
        "gateway_tenant_ref": str(tenant.gateway_tenant_ref),
    }
