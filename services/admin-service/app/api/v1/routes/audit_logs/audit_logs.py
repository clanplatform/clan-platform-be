from typing import Optional
from datetime import datetime
from uuid import UUID
import os
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
import httpx

from app.core.config import settings
from app.core.security import get_current_user

REQUIRE_AUTH = os.getenv("REQUIRE_AUTH", "false").lower() == "true"


def require_admin_role(current_user=Depends(get_current_user)):
    if not REQUIRE_AUTH:
        return current_user
    return current_user


router = APIRouter()


@router.get("", summary="List audit logs")
def list_audit_logs(
    tenant_id: Optional[UUID] = Query(None, description="Filter by tenant UUID"),
    user_id: Optional[UUID] = Query(None, description="Filter by user UUID"),
    action: Optional[str] = Query(None, max_length=100, description="CREATE / UPDATE / DELETE / READ"),
    object_type: Optional[str] = Query(None, max_length=100, description="Domain / Department / Entity / …"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    current_user=Depends(require_admin_role),
):
    """Retrieve audit logs with optional filters (proxied from audit service)."""
    params = {k: v for k, v in {
        "tenant_id": str(tenant_id) if tenant_id else None,
        "user_id": str(user_id) if user_id else None,
        "action": action,
        "object_type": object_type,
        "skip": skip,
        "limit": limit,
    }.items() if v is not None}

    try:
        resp = httpx.get(
            f"{settings.AUDIT_SERVICE_URL}/api/v1/logs",
            params=params,
            timeout=10.0,
        )
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            media_type="application/json",
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Audit service unavailable: {exc}")


@router.get("/export", summary="Export audit logs as Excel or PDF")
def export_audit_logs(
    file_format: str = Query("excel", alias="format", pattern="^(excel|pdf)$", description="excel or pdf"),
    tenant_id: Optional[UUID] = Query(None, description="Filter by tenant UUID"),
    user_id: Optional[UUID] = Query(None, description="Filter by user UUID"),
    action: Optional[str] = Query(None, max_length=100, description="CREATE / UPDATE / DELETE / READ"),
    object_type: Optional[str] = Query(None, max_length=100, description="Domain / Department / Entity / …"),
    date_from: Optional[datetime] = Query(None, description="Start date (ISO 8601, e.g. 2026-01-01T00:00:00)"),
    date_to: Optional[datetime] = Query(None, description="End date (ISO 8601, e.g. 2026-12-31T23:59:59)"),
    limit: int = Query(5000, ge=1, le=10000, description="Max rows to export (default 5000)"),
    current_user=Depends(require_admin_role),
):
    """
    Download audit logs as **Excel** (.xlsx) or **PDF**.

    - `format=excel` — returns an `.xlsx` file with all columns
    - `format=pdf`   — returns a landscape A4 PDF
    """
    params = {k: v for k, v in {
        "format": file_format,
        "tenant_id": str(tenant_id) if tenant_id else None,
        "user_id": str(user_id) if user_id else None,
        "action": action,
        "object_type": object_type,
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "limit": limit,
    }.items() if v is not None}

    try:
        resp = httpx.get(
            f"{settings.AUDIT_SERVICE_URL}/api/v1/logs/export",
            params=params,
            timeout=60.0,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail="Export failed at audit service")

        ext = "pdf" if file_format == "pdf" else "xlsx"
        filename = resp.headers.get(
            "content-disposition",
            f"attachment; filename=audit_logs.{ext}",
        )
        return StreamingResponse(
            iter([resp.content]),
            media_type=resp.headers.get("content-type", "application/octet-stream"),
            headers={"Content-Disposition": filename},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Audit service unavailable: {exc}")
