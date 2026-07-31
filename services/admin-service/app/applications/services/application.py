from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from app.applications.models.application import Application
from app.applications.schemas.application import ApplicationCreate, ApplicationUpdate
from app.applications.exceptions import (
    ApplicationNotFoundError,
    DuplicateApplicationNameError,
    ApplicationReadOnlyError,
)
from app.domains.exceptions import DomainNotFoundError
from app.domains.services.domain import get_domain_by_name, get_domain
from app.core.hybrid_encryption import hybrid_encryption
from app.core.access import is_active_from_access as _is_active_from_access, is_write_locked as _is_write_locked
from app.infrastructure.audit_tenant import fire_audit_log

def get_application(db: Session, application_id: uuid.UUID) -> Optional[Application]:
    """Get an application by ID"""
    application = db.query(Application).filter(Application.id == application_id).first()


def is_application_write_locked(db: Session, application_id: uuid.UUID) -> bool:
    """Return True if the given application's access is read-only/disabled."""
    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        return False
    return _is_write_locked(app.access)

def ensure_application_writable(db: Session, application_id: uuid.UUID, resource: str = "this resource") -> None:
    """
    Raise 403 when the parent application is read-only.

    Used to gate writes to an application's child resources (modules, menus).
    """
    if is_application_write_locked(db, application_id):
        raise ApplicationReadOnlyError(resource)

def get_all_applications(db: Session, skip: int = 0, limit: int = 100) -> List[Application]:
    """Get all applications with pagination"""
    applications = db.query(Application).offset(skip).limit(limit).all()
    return applications

def fetch_applications_by_domain_name(
    db: Session, domain_name: str, application_name: Optional[str] = None, skip: int = 0, limit: int = 100
) -> List[Application]:
    """
    Fetch applications by domain name with optional filtering by application name.
    Supports pagination.
    """
    # First get the domain by name to get its ID
    domain = get_domain_by_name(db, domain_name=domain_name)
    if not domain:
        return []
    
    query = db.query(Application).filter(Application.domain_id == domain.id)
    if application_name:
        query = query.filter(Application.name == application_name)
    applications = query.offset(skip).limit(limit).all()
    return applications

def fetch_applications_by_domain_id(
    db: Session, domain_id: uuid.UUID, application_name: Optional[str] = None, skip: int = 0, limit: int = 100
) -> List[Application]:
    """
    Fetch applications by domain ID with optional filtering by application name.
    Supports pagination.
    """
    query = db.query(Application).filter(Application.domain_id == domain_id)
    if application_name:
        query = query.filter(Application.name == application_name)
    applications = query.offset(skip).limit(limit).all()
    return applications





def create_application(db: Session, application: ApplicationCreate, user_id: Optional[uuid.UUID] = None) -> Application:
    """Create a new application"""
    # Check if domain exists by domain_id
    domain = get_domain(db, domain_id=application.domain_id)
    if not domain:
        raise DomainNotFoundError()

    # Check if application name already exists in this domain
    existing_applications = fetch_applications_by_domain_id(
        db, domain_id=application.domain_id
    )
    if any(app.name == application.name for app in existing_applications):
        raise DuplicateApplicationNameError()

    # Access drives the active state: "disable" forces it off, "write"/"read"
    # keep it on; otherwise fall back to the value supplied on the request.
    derived_active = _is_active_from_access(application.access)
    is_active = derived_active if derived_active is not None else application.is_active

    # Create new application
    db_application = Application(
        name=application.name,
        description=application.description,
        version=application.version,
        status=application.status,
        domain_id=application.domain_id,
        is_active=is_active,
        key=application.key,
        label=application.label,
        route=application.route,
        icon=application.icon,
        badge=application.badge,
        section_title=application.section_title,
        access=application.access,
        order_index=application.order_index,
    )
    db.add(db_application)
    db.commit()
    db.refresh(db_application)
    fire_audit_log(
        action="CREATE", object_type="Application",
        object_id=str(db_application.id),
        user_id=str(user_id) if user_id else None,
        new_values={"name": db_application.name, "domain_id": str(db_application.domain_id)},
    )
    return db_application

def update_application(db: Session, application_id: uuid.UUID, application: ApplicationUpdate, user_id: Optional[uuid.UUID] = None) -> Application:
    """Update an application"""
    db_application = get_application(db, application_id=application_id)
    if not db_application:
        raise ApplicationNotFoundError()

    update_data = application.dict(exclude_unset=True)

    # Read-only lock: a write-locked app (access has no "write") can only be
    # edited by a payload that changes "access" itself (the way to unlock it).
    if _is_write_locked(db_application.access) and "access" not in update_data:
        raise ApplicationReadOnlyError()

    # Check if the domain exists when being updated
    if "domain_id" in update_data:
        domain = get_domain(db, domain_id=update_data["domain_id"])
        if not domain:
            raise DomainNotFoundError()

    # Check for unique application name within the domain if being updated
    if "name" in update_data and update_data["name"] != db_application.name:
        domain_id = update_data.get("domain_id", db_application.domain_id)
        existing_apps = fetch_applications_by_domain_id(
            db, domain_id=domain_id, application_name=update_data["name"]
        )
        if existing_apps:
            raise DuplicateApplicationNameError()

    # Keep is_active in sync when access changes: "disable" forces it off,
    # "write"/"read" keep it on (access wins over any is_active in the payload).
    if "access" in update_data:
        derived_active = _is_active_from_access(update_data.get("access"))
        if derived_active is not None:
            update_data["is_active"] = derived_active

    # Update the application fields
    for key, value in update_data.items():
        setattr(db_application, key, value)

    db.add(db_application)
    db.commit()
    db.refresh(db_application)
    fire_audit_log(
        action="UPDATE", object_type="Application",
        object_id=str(application_id),
        user_id=str(user_id) if user_id else None,
        new_values=update_data,
    )
    return db_application


def delete_application(db: Session, application_id: uuid.UUID, user_id: Optional[uuid.UUID] = None) -> None:
    """Delete an application"""
    db_application = get_application(db, application_id=application_id)
    if not db_application:
        raise ApplicationNotFoundError()
    
    db.delete(db_application)
    db.commit()
    fire_audit_log(
        action="DELETE", object_type="Application",
        object_id=str(application_id),
        user_id=str(user_id) if user_id else None,
    )
    return None
