"""
HTTP client for clan-api-gateway-be gateway-service.

Call sync_tenant_to_gateway() after every successful Tenant CREATE or UPDATE so
the gateway's tenant registry (Envoy routing / slug / per-tenant rate limits)
stays in sync with the platform-domain tenant registry.

Hits the gateway's internal POST /api/v1/sync/tenants endpoint, authenticated
with the shared x-internal-api-key header. Failures are always swallowed — a
sync error must never roll back or fail the caller.
Use asyncio.create_task(sync_tenant_to_gateway(...)) for true fire-and-forget.
"""
import logging
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


async def sync_tenant_to_gateway(
    *,
    tenant_id: str,
    tenant_name: str,
    tenant_code: Optional[str] = None,
    is_active: bool = True,
) -> None:
    """
    Upsert the tenant into clan-api-gateway-be so Envoy routing stays aligned
    with the platform-domain registry. Fire-and-forget — never raises.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as http:
            resp = await http.post(
                f"{settings.GATEWAY_SERVICE_URL}/api/v1/sync/tenants",
                headers={"x-internal-api-key": settings.INTERNAL_API_KEY},
                json={
                    "tenant_id":         tenant_id,
                    "tenant_name":       tenant_name,
                    "tenant_code":       tenant_code,
                    "is_active":         is_active,
                },
            )
            if resp.status_code in (200, 201):
                logger.info("[gateway-sync] tenant %s synced to gateway", tenant_id)
            else:
                logger.warning(
                    "[gateway-sync] tenant %s rejected by gateway: %s %s",
                    tenant_id, resp.status_code, resp.text[:200],
                )
    except Exception as exc:
        logger.error("[gateway-sync] sync_tenant_to_gateway failed for %s: %s", tenant_id, exc)
