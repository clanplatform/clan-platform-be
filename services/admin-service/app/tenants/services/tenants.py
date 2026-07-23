from typing import List, Optional, TYPE_CHECKING, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from uuid import UUID

from app.tenants.models.tenants import Tenant
from app.tenants.schemas.tenants import TenantCreate, TenantUpdate
from app.core.hybrid_encryption import hybrid_encryption
from app.infrastructure.audit_tenant import fire_audit_log

# TODO: TenantApplication and DomainApplication models and schemas need to be created
# Placeholder types for now - functions using these will raise NotImplementedError
if TYPE_CHECKING:
    TenantApplication = None
    DomainApplication = None
    TenantApplicationCreate = None
    TenantApplicationUpdate = None
    DomainApplicationCreate = None
    DomainApplicationUpdate = None
else:
    TenantApplication = type('TenantApplication', (), {})
    DomainApplication = type('DomainApplication', (), {})
    TenantApplicationCreate = type('TenantApplicationCreate', (), {})
    TenantApplicationUpdate = type('TenantApplicationUpdate', (), {})
    DomainApplicationCreate = type('DomainApplicationCreate', (), {})
    DomainApplicationUpdate = type('DomainApplicationUpdate', (), {})

# Tenant CRUD operations
def get_tenant(db: Session, tenant_id: UUID) -> Optional[Tenant]:
    """Get a tenant by ID"""
    tenant = db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
    return tenant

def get_tenant_by_email(db: Session, email: str) -> Optional[Tenant]:
    """Get a tenant by email"""
    return db.query(Tenant).filter(Tenant.email == email).first()

def get_tenant_by_company_name(db: Session, company_name: str) -> Optional[Tenant]:
    """Get a tenant by company name"""
    return db.query(Tenant).filter(Tenant.company_name == company_name).first()

def get_tenants(db: Session, skip: int = 0, limit: int = 100, active_only: bool = True) -> List[Tenant]:
    """Get multiple tenants with pagination"""
    query = db.query(Tenant)

    if active_only:
        query = query.filter(Tenant.active == "true", Tenant.deleted == "N")

    tenants = query.offset(skip).limit(limit).all()

    return tenants

def get_tenants_by_domain(db: Session, domain_id: int, skip: int = 0, limit: int = 100) -> List[Tenant]:
    """Get tenants by domain ID"""
    tenants = db.query(Tenant).join(Tenant.domains).filter(
        Tenant.domains.any(domain_id=domain_id),
        Tenant.active == "true",
        Tenant.deleted == "N"
    ).offset(skip).limit(limit).all()

    return tenants

def create_tenant(db: Session, tenant: TenantCreate, user_id: Optional[UUID] = None) -> Tenant:
    """Create a new tenant and provision its dedicated database."""
    existing_tenant = get_tenant_by_email(db, tenant.email)
    if existing_tenant:
        raise ValueError(f"Tenant with email {tenant.email} already exists")

    existing_company = get_tenant_by_company_name(db, tenant.company_name)
    if existing_company:
        raise ValueError(f"Tenant with company name {tenant.company_name} already exists")

    # Creator credentials are verification-only fields — never stored on the row
    db_tenant = Tenant(**tenant.model_dump(
        exclude={"created_by_email", "created_by_password"}
    ))

    # Determine the tenant-specific database name.
    # Prefer the explicit tenant_db_name from the request; fall back to a name
    # derived from tenant_code (or tenant_id) when it is not supplied.
    # Always slugify — the name is embedded directly into CREATE DATABASE.
    from app.infrastructure.database.tenant_db_manager import TenantDatabaseManager, _slugify
    if db_tenant.tenant_db_name and db_tenant.tenant_db_name.strip():
        db_tenant.tenant_db_name = _slugify(db_tenant.tenant_db_name.strip())
    else:
        tenant_code = (db_tenant.tenant_code or str(db_tenant.tenant_id)).strip()
        db_tenant.tenant_db_name = TenantDatabaseManager.make_db_name(tenant_code)

    db.add(db_tenant)
    db.commit()
    db.refresh(db_tenant)

    # Provision: CREATE DATABASE + create all tables
    from app.infrastructure.database.tenant_db_manager import tenant_db_manager
    from app.core.config import settings
    ok = tenant_db_manager.provision(db_tenant.tenant_db_name, settings.DATABASE_URL)
    if not ok:
        import logging
        logging.getLogger(__name__).warning(
            "Tenant %s created but database provisioning failed — "
            "run provisioning manually.", db_tenant.tenant_id
        )

    fire_audit_log(
        action="CREATE", object_type="Tenant",
        object_id=str(db_tenant.tenant_id),
        tenant_id=str(db_tenant.tenant_id),
        user_id=str(user_id) if user_id else None,
        new_values={
            "tenant_name": db_tenant.tenant_name,
            "contact_email": db_tenant.contact_email,
            "tenant_db_name": db_tenant.tenant_db_name,
        },
    )
    return db_tenant

def update_tenant(db: Session, tenant_id: UUID, tenant_update: TenantUpdate, user_id: Optional[UUID] = None) -> Optional[Tenant]:
    """Update an existing tenant"""
    db_tenant = get_tenant(db, tenant_id)
    if not db_tenant:
        return None

    if tenant_update.email and tenant_update.email != db_tenant.email:
        existing_tenant = get_tenant_by_email(db, tenant_update.email)
        if existing_tenant and existing_tenant.tenant_id != tenant_id:
            raise ValueError(f"Tenant with email {tenant_update.email} already exists")

    if tenant_update.company_name and tenant_update.company_name != db_tenant.company_name:
        existing_company = get_tenant_by_company_name(db, tenant_update.company_name)
        if existing_company and existing_company.tenant_id != tenant_id:
            raise ValueError(f"Tenant with company name {tenant_update.company_name} already exists")

    update_data = tenant_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_tenant, field, value)

    db.commit()
    db.refresh(db_tenant)
    fire_audit_log(
        action="UPDATE", object_type="Tenant",
        object_id=str(tenant_id),
        tenant_id=str(tenant_id),
        user_id=str(user_id) if user_id else None,
        new_values=update_data,
    )
    return db_tenant

def delete_tenant(db: Session, tenant_id: UUID, user_id: Optional[UUID] = None) -> bool:
    """Soft delete a tenant (mark as deleted)"""
    db_tenant = get_tenant(db, tenant_id)
    if not db_tenant:
        return False

    db_tenant.deleted = "Y"
    db_tenant.active = "false"
    db.commit()
    fire_audit_log(
        action="DELETE", object_type="Tenant",
        object_id=str(tenant_id),
        tenant_id=str(tenant_id),
        user_id=str(user_id) if user_id else None,
        old_values={"deleted": "N"}, new_values={"deleted": "Y"},
    )
    return True

def hard_delete_tenant(db: Session, tenant_id: UUID) -> bool:
    """Hard delete a tenant (permanently remove from database)"""
    db_tenant = get_tenant(db, tenant_id)
    if not db_tenant:
        return False

    db.delete(db_tenant)
    db.commit()
    return True

# Tenant Application CRUD operations
def get_tenant_application(db: Session, tenant_id: UUID, app_id: int) -> Optional[TenantApplication]:
    """Get a tenant-application mapping"""
    raise NotImplementedError("TenantApplication model not yet implemented")

def get_tenant_applications(db: Session, tenant_id: UUID) -> List[TenantApplication]:
    """Get all applications for a tenant"""
    return db.query(TenantApplication).filter(
        TenantApplication.tenant_id == tenant_id
    ).all()

def get_application_tenants(db: Session, app_id: int) -> List[TenantApplication]:
    """Get all tenants for an application"""
    return db.query(TenantApplication).filter(
        TenantApplication.app_id == app_id
    ).all()

def create_tenant_application(db: Session, tenant_app: TenantApplicationCreate) -> TenantApplication:
    """Create a new tenant-application mapping"""
    existing_mapping = get_tenant_application(db, tenant_app.tenant_id, tenant_app.app_id)
    if existing_mapping:
        raise ValueError(f"Tenant-Application mapping already exists for tenant {tenant_app.tenant_id} and app {tenant_app.app_id}")

    db_tenant_app = TenantApplication(**tenant_app.model_dump())
    db.add(db_tenant_app)
    db.commit()
    db.refresh(db_tenant_app)
    return db_tenant_app

def update_tenant_application(db: Session, tenant_id: UUID, app_id: int, tenant_app_update: TenantApplicationUpdate) -> Optional[TenantApplication]:
    """Update a tenant-application mapping"""
    db_tenant_app = get_tenant_application(db, tenant_id, app_id)
    if not db_tenant_app:
        return None

    update_data = tenant_app_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_tenant_app, field, value)

    db.commit()
    db.refresh(db_tenant_app)
    return db_tenant_app

def delete_tenant_application(db: Session, tenant_id: UUID, app_id: int) -> bool:
    """Delete a tenant-application mapping"""
    db_tenant_app = get_tenant_application(db, tenant_id, app_id)
    if not db_tenant_app:
        return False

    db.delete(db_tenant_app)
    db.commit()
    return True

# Domain Application CRUD operations
def get_domain_application(db: Session, domain_id: int, app_id: int) -> Optional[DomainApplication]:
    """Get a domain-application mapping"""
    return db.query(DomainApplication).filter(
        DomainApplication.domain_id == domain_id,
        DomainApplication.app_id == app_id
    ).first()

def get_domain_applications(db: Session, domain_id: int) -> List[DomainApplication]:
    """Get all applications for a domain"""
    return db.query(DomainApplication).filter(
        DomainApplication.domain_id == domain_id
    ).all()

def get_application_domains(db: Session, app_id: int) -> List[DomainApplication]:
    """Get all domains for an application"""
    return db.query(DomainApplication).filter(
        DomainApplication.app_id == app_id
    ).all()

def create_domain_application(db: Session, domain_app: DomainApplicationCreate) -> DomainApplication:
    """Create a new domain-application mapping"""
    existing_mapping = get_domain_application(db, domain_app.domain_id, domain_app.app_id)
    if existing_mapping:
        raise ValueError(f"Domain-Application mapping already exists for domain {domain_app.domain_id} and app {domain_app.app_id}")

    db_domain_app = DomainApplication(**domain_app.model_dump())
    db.add(db_domain_app)
    db.commit()
    db.refresh(db_domain_app)
    return db_domain_app

def update_domain_application(db: Session, domain_id: int, app_id: int, domain_app_update: DomainApplicationUpdate) -> Optional[DomainApplication]:
    """Update a domain-application mapping"""
    db_domain_app = get_domain_application(db, domain_id, app_id)
    if not db_domain_app:
        return None

    update_data = domain_app_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_domain_app, field, value)

    db.commit()
    db.refresh(db_domain_app)
    return db_domain_app

def delete_domain_application(db: Session, domain_id: int, app_id: int) -> bool:
    """Delete a domain-application mapping"""
    db_domain_app = get_domain_application(db, domain_id, app_id)
    if not db_domain_app:
        return False

    db.delete(db_domain_app)
    db.commit()
    return True

# Hierarchical data retrieval functions
def get_tenant_hierarchy(db: Session, tenant_id: UUID) -> dict:
    """Get complete hierarchy for a tenant: Tenant -> Domains -> Applications"""
    tenant = get_tenant(db, tenant_id)
    if not tenant:
        return None

    domains = get_tenants_by_domain(db, tenant.domain_id) if tenant.domain_id else []

    hierarchy = {
        "tenant": tenant,
        "domains": []
    }

    for domain in domains:
        domain_apps = get_domain_applications(db, domain.id)
        hierarchy["domains"].append({
            "domain": domain,
            "applications": domain_apps
        })

    return hierarchy

def get_domain_hierarchy(db: Session, domain_id: int) -> dict:
    """Get complete hierarchy for a domain: Domain -> Applications -> Tenants"""
    from app.domains.services.domain import get_domain

    domain = get_domain(db, domain_id)
    if not domain:
        return None

    domain_apps = get_domain_applications(db, domain_id)
    tenants = get_tenants_by_domain(db, domain_id)

    hierarchy = {
        "domain": domain,
        "applications": domain_apps,
        "tenants": tenants
    }

    return hierarchy
