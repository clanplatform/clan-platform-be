"""
HTTP client for clan-tenant-portal-be.

Call sync_tenant_profile() after every successful Tenant CREATE or UPDATE.
Failures are always swallowed — a sync error must never roll back the caller.
Use asyncio.create_task(sync_tenant_profile(...)) for true fire-and-forget.
"""
import asyncio
import logging
import uuid as _uuid
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


async def sync_tenant_profile(
    *,
    tenant_id: str,
    tenant_name: str,
    tenant_code: Optional[str] = None,
    contact_email: Optional[str] = None,
    contact_phone: Optional[str] = None,
    is_active: bool = True,
) -> None:
    """
    Push tenant data to clan-tenant-portal-be so its TenantProfile stays in sync.
    Called after Tenant CREATE and UPDATE. Fire-and-forget — never raises.
    Callers: asyncio.create_task(sync_tenant_profile(...))
    """
    try:
        async with httpx.AsyncClient(timeout=3.0) as http:
            resp = await http.post(
                f"{settings.TENANT_PORTAL_SERVICE_URL}/api/v1/sync/tenants",
                headers={"x-internal-key": settings.INTERNAL_API_KEY},
                json={
                    "tenant_id":         tenant_id,
                    "tenant_name":       tenant_name,
                    "tenant_code":       tenant_code,
                    "contact_email":     contact_email,
                    "contact_phone":     contact_phone,
                    "is_active":         is_active,
                },
            )
            if resp.status_code in (200, 201):
                portal_id = resp.json().get("id")
                if portal_id:
                    await _store_gateway_ref(tenant_id, portal_id)
    except Exception as exc:
        logger.error("[tenant-sync] sync_tenant_profile failed for %s: %s", tenant_id, exc)


async def _store_gateway_ref(tenant_id: str, portal_id: str) -> None:
    """Back-fill Tenant.gateway_tenant_ref once the portal returns its UUID."""
    try:
        from app.infrastructure.database.session import SessionLocal
        from app.tenants.models.tenants import Tenant

        with SessionLocal() as db:
            t = db.query(Tenant).filter(
                Tenant.tenant_id == _uuid.UUID(tenant_id)
            ).first()
            if t and t.gateway_tenant_ref is None:
                t.gateway_tenant_ref = _uuid.UUID(portal_id)
                db.commit()
    except Exception as exc:
        logger.error("[tenant-sync] gateway_tenant_ref update failed: %s", exc)
