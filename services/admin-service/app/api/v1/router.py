"""
API v1 router - combines all v1 endpoints
"""
from fastapi import APIRouter
from app.api.v1.routes.domains.domains import router as domains_router
from app.api.v1.routes.applications.applications import router as applications_router
from app.api.v1.routes.org_structure.tenants import router as tenants_router
from app.api.v1.routes.org_structure.entity import router as entity_router
from app.api.v1.routes.org_structure.departments import router as department_router
from app.api.v1.routes.org_structure.divisions import router as division_router
from app.api.v1.routes.org_structure.job_codes import router as job_code_router
from app.api.v1.routes.navigation.module import router as modules_router
from app.api.v1.routes.navigation.menu import router as menus_router
from app.api.v1.routes.forms.forms import router as forms_router
from app.api.v1.routes.navigation.menu_language import router as menus_language_router
from app.api.v1.routes.forms.form_language import router as forms_language_router
from app.api.v1.routes.access_control.user_role import router as user_role_router
from app.api.v1.routes.access_control.user_setup import router as user_setup_router
from app.api.v1.routes.access_control.user_role_form_permission import router as user_role_form_permission_router
from app.api.v1.routes.audit_logs.audit_logs import router as audit_logs_router
from app.api.v1.routes.navigation.button import router as buttons_router
from app.api.v1.routes.org_structure.tenant_modules import router as tenant_modules_router
from app.api.v1.routes.sync.tenants import router as sync_tenants_router
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

# Include menus_language routes
api_v1_router.include_router(
    menus_language_router,
    prefix="/menus_language",
    tags=["menus_language"]
)

# Include forms routes
api_v1_router.include_router(
    forms_router,
    prefix="/forms",
    tags=["forms"]
)

# Include forms_language routes
api_v1_router.include_router(
    forms_language_router,
    prefix="/forms_language",
    tags=["forms_language"]
)

#include tenant routes
api_v1_router.include_router(
    tenants_router,
    prefix="/tenants",
    tags=["tenants"]
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

#include user_role routes
api_v1_router.include_router(
    user_role_router,
    prefix="/user_role",
    tags=["user_role"]
)

#include user_role_form_permission routes
api_v1_router.include_router(
    user_role_form_permission_router,
    prefix="/user_role_form_permission",
    tags=["user_role_form_permission"]
)

#include user_setup routes
api_v1_router.include_router(
    user_setup_router,
    prefix="/user_setup",
    tags=["user_setup"]
)

# include audit logs routes
api_v1_router.include_router(
    audit_logs_router,
    prefix="/audit-logs",
    tags=["audit-logs"]
)

# include buttons routes
api_v1_router.include_router(
    buttons_router,
    prefix="/buttons",
    tags=["buttons"]
)

# include tenant-module assignment routes
api_v1_router.include_router(
    tenant_modules_router,
    prefix="/tenant_modules",
    tags=["tenant_modules"]
)

# inbound sync from clan-tenant-portal-be (service-to-service, no JWT)
api_v1_router.include_router(
    sync_tenants_router,
    prefix="/sync",
    tags=["sync"],
)
