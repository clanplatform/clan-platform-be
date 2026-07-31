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
from app.api.v1.routes.audit_logs.audit_logs import router as audit_logs_router
from app.api.v1.routes.navigation.button import router as buttons_router
from app.api.v1.routes.org_structure.tenant_modules import router as tenant_modules_router
from app.api.v1.routes.org_structure.tenant_applications import router as tenant_applications_router
from app.api.v1.routes.sync.tenants import router as sync_tenants_router
from app.api.v1.routes.master_datas.master_countries import router as master_countries_router
from app.api.v1.routes.master_datas.master_states import router as master_states_router
from app.api.v1.routes.master_datas.master_cities import router as master_cities_router
from app.api.v1.routes.master_datas.master_languages import router as master_languages_router
from app.api.v1.routes.master_datas.master_locales import router as master_locales_router
from app.api.v1.routes.onboarding.onboarding import router as onboarding_router
from app.api.v1.routes.subscription.subscription import router as subscription_router
from app.api.v1.routes.security.security import router as security_router
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

# include tenant-application assignment routes
api_v1_router.include_router(
    tenant_applications_router,
    prefix="/tenant_applications",
    tags=["tenant_applications"]
)

# inbound sync from clan-tenant-portal-be (service-to-service, no JWT)
api_v1_router.include_router(
    sync_tenants_router,
    prefix="/sync",
    tags=["sync"],
)

# include master country routes
api_v1_router.include_router(
    master_countries_router,
    prefix="/master_countries",
    tags=["master_countries"],
)

# include master state routes
api_v1_router.include_router(
    master_states_router,
    prefix="/master_states",
    tags=["master_states"],
)

# include master city routes
api_v1_router.include_router(
    master_cities_router,
    prefix="/master_cities",
    tags=["master_cities"],
)

# include master language routes
api_v1_router.include_router(
    master_languages_router,
    prefix="/master_languages",
    tags=["master_languages"],
)

# include master locale routes
api_v1_router.include_router(
    master_locales_router,
    prefix="/master_locales",
    tags=["master_locales"],
)

# include onboarding routes (step-form client creation)
api_v1_router.include_router(
    onboarding_router,
    prefix="/onboarding",
    tags=["onboarding"],
)

# include subscription routes
api_v1_router.include_router(
    subscription_router,
    prefix="/subscription",
    tags=["subscription"],
)

# include security routes
api_v1_router.include_router(
    security_router,
    prefix="/security",
    tags=["security"],
)
