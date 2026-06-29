"""
HTTP client for clan-tenant-portal-be.

Call sync_tenant_profile() after every successful Client CREATE or UPDATE.
Failures are always swallowed — a sync error must never roll back the caller.
Use asyncio.create_task(sync_tenant_profile(...)) for true fire-and-forget.
"""
import asyncio
import logging
import httpx
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


async def sync_tenant_profile(
    *,
    client_id: str,
    client_name: str,
    client_code: Optional[str] = None,
    contact_email: Optional[str] = None,
    contact_phone: Optional[str] = None,
    subscription_plan: Optional[str] = None,
    is_active: bool = True,
) -> None:
    """
    Push client data to clan-api-gateway-be so TenantProfile stays in sync.
    Called after Client CREATE and UPDATE. Fire-and-forget — never raises.
    Callers should use: asyncio.create_task(sync_tenant_profile(...))
    """
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.post(
                f"{settings.TENANT_PORTAL_SERVICE_URL}/api/v1/sync/tenants",
                headers={"X-Internal-Api-Key": settings.INTERNAL_API_KEY},
                json={
                    "client_id":         client_id,
                    "client_name":       client_name,
                    "client_code":       client_code,
                    "contact_email":     contact_email,
                    "contact_phone":     contact_phone,
                    "subscription_plan": subscription_plan,
                    "is_active":         is_active,
                },
            )
    except Exception as exc:
        logger.error(
            "[tenant-sync] sync_tenant_profile failed for client %s: %s",
            client_id, exc
        )
