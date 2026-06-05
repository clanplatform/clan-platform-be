"""
API v1 router - combines all v1 endpoints
"""
from fastapi import APIRouter
from app.api.v1.routes.domains.domains import router as domains_router
from app.api.v1.routes.applications.applications import router as applications_router
from app.api.v1.routes.org_structure.clients import router as clients_router
from app.api.v1.routes.org_structure.entity import router as entity_router
from app.api.v1.routes.org_structure.departments import router as department_router
from app.api.v1.routes.org_structure.divisions import router as division_router
from app.api.v1.routes.org_structure.job_codes import router as job_code_router
from app.api.v1.routes.navigation.module import router as modules_router
from app.api.v1.routes.navigation.menu import router as menus_router
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

# Include modules routes
api_v1_router.include_router(
    modules_router,
    prefix="/modules",
    tags=["modules"]
)

# Include menus routes
api_v1_router.include_router(
    menus_router,
    prefix="/menus",
    tags=["menus"]
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

#include departments routes
api_v1_router.include_router(
    department_router,
    prefix="/departments",
    tags=["departments"]
)

#include divisions routes
api_v1_router.include_router(
    division_router,
    prefix="/divisions",
    tags=["divisions"]
)

#include job-code routes
api_v1_router.include_router(
    job_code_router,
    prefix="/job_codes",
    tags=["job_codes"]
)
