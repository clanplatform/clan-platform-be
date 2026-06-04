"""
API v1 router - combines all v1 endpoints
"""
from fastapi import APIRouter
from app.api.v1.routes.domains.domains import router as domains_router
from app.api.v1.routes.applications.applications import router as applications_router
from app.api.v1.routes.org_structure.clients import router as clients_router
from app.api.v1.routes.org_structure.entity import router as entity_router
# Create v1 API router
api_v1_router = APIRouter(prefix="/api/v1")

# Include domain routes
api_v1_router.include_router(
    domains_router,
    prefix="/domains",
    tags=["domains"]
)

# Include application routes
api_v1_router.include_router(
    applications_router,
    prefix="/applications",
    tags=["applications"]
)

#include client routes
api_v1_router.include_router(
    clients_router,
    prefix="/clients",
    tags=["clients"]
)

#include entity routes
api_v1_router.include_router(
    entity_router,
    prefix="/entity",
    tags=["entity"]
)
