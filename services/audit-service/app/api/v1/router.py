from fastapi import APIRouter
from app.api.v1.routes.audit.audit_logs import router as audit_logs_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(
    audit_logs_router,
    prefix="/logs",
    tags=["audit-logs"],
)
