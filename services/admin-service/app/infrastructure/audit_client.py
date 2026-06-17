"""
HTTP client for the audit-service.

Call fire_audit_log() after any successful CREATE / UPDATE / DELETE / RESTORE.
Failures are always swallowed — a logging error must never roll back the caller.
"""
import httpx
from typing import Optional, Dict, Any
from app.core.config import settings


def fire_audit_log(
    *,
    action: str,
    object_type: str,
    object_id: Optional[str] = None,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    entity_id: Optional[str] = None,
    old_values: Optional[Dict[str, Any]] = None,
    new_values: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    session_id: Optional[str] = None,
) -> None:
    """
    POST a single audit log entry to the audit-service.

    Standard action values:
        CREATE | UPDATE | DELETE | RESTORE | LOGIN | LOGOUT
    """
    try:
        httpx.post(
            f"{settings.AUDIT_SERVICE_URL}/api/v1/logs",
            json={
                "action": action,
                "object_type": object_type,
                "object_id": object_id,
                "client_id": client_id,
                "user_id": user_id,
                "entity_id": entity_id,
                "old_values": old_values or {},
                "new_values": new_values or {},
                "ip_address": ip_address,
                "session_id": session_id,
            },
            timeout=2.0,
        )
    except Exception as exc:
        print(f"[audit-client] fire_audit_log failed: {exc}")
