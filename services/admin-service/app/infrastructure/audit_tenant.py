"""
HTTP client for the audit-service.

Call fire_audit_log() after any successful CREATE / UPDATE / DELETE / RESTORE.
Failures are always swallowed — a logging error must never roll back the caller.
"""
import httpx
from typing import Optional, Dict, Any
from fastapi.encoders import jsonable_encoder
from app.core.config import settings


def fire_audit_log(
    *,
    action: str,
    object_type: str,
    object_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    entity_id: Optional[str] = None,
    old_values: Optional[Dict[str, Any]] = None,
    new_values: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    session_id: Optional[str] = None,
    risk_score: Optional[str] = None,
) -> None:
    """
    POST a single audit log entry to the audit-service.

    Standard action values:
        CREATE | UPDATE | DELETE | RESTORE | LOGIN | LOGOUT
    """
    try:
        # old_values/new_values are frequently a raw model_dump() from callers
        # (UUID/Decimal/datetime fields, not the JSON-safe str/float/isoformat
        # forms) — jsonable_encoder normalizes the whole payload so a type
        # httpx's json= can't natively serialize doesn't silently drop the
        # entire audit entry.
        httpx.post(
            f"{settings.AUDIT_SERVICE_URL}/api/v1/logs",
            json=jsonable_encoder({
                "action": action,
                "object_type": object_type,
                "object_id": object_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "entity_id": entity_id,
                "old_values": old_values or {},
                "new_values": new_values or {},
                "ip_address": ip_address,
                "user_agent": user_agent,
                "session_id": session_id,
                "risk_score": risk_score,
            }),
            timeout=2.0,
        )
    except Exception as exc:
        print(f"[audit-client] fire_audit_log failed: {exc}")
