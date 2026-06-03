from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List, Optional
import uuid

from app.models.application import Application
from app.schemas.application import ApplicationCreate, ApplicationUpdate
from app.crud.domain import get_domain_by_name, get_domain
from app.core.hybrid_encryption import hybrid_encryption

def get_application(db: Session, application_id: uuid.UUID) -> Optional[Application]:
    """Get an application by ID"""
    application = db.query(Application).filter(Application.id == application_id).first()
    if application:
        _decrypt_application_fields(application)
    return application

def _decrypt_application_fields(application: Application) -> None:
    """Decrypt sensitive fields in application object"""
    if application.config:
        try:
            application.config = hybrid_encryption.decrypt_sensitive_field(application.config)
        except Exception:
            # If decryption fails, the field might not be encrypted (legacy data)
            pass

def get_all_applications(db: Session, skip: int = 0, limit: int = 100) -> List[Application]:
    """Get all applications with pagination"""
    applications = db.query(Application).offset(skip).limit(limit).all()
    for application in applications:
        _decrypt_application_fields(application)
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
    for application in applications:
        _decrypt_application_fields(application)
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
    for application in applications:
        _decrypt_application_fields(application)
    return applications





def create_application(db: Session, application: ApplicationCreate) -> Application:
    """Create a new application"""
    # Check if domain exists by domain_id
    domain = get_domain(db, domain_id=application.domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    # Check if application name already exists in this domain
    existing_applications = fetch_applications_by_domain_id(
        db, domain_id=application.domain_id
    )
    if any(app.name == application.name for app in existing_applications):
        raise HTTPException(status_code=400, detail="Application name already exists in this domain")

    # Encrypt sensitive fields
    encrypted_config = None
    if application.config:
        encrypted_config = hybrid_encryption.encrypt_sensitive_field(application.config)

    # Create new application
    db_application = Application(
        name=application.name,
        description=application.description,
        version=application.version,
        status=application.status,
        domain_id=application.domain_id,
        config=encrypted_config,
        is_active=application.is_active,
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
    return db_application

def update_application(db: Session, application_id: uuid.UUID, application: ApplicationUpdate) -> Application:
    """Update an application"""
    db_application = get_application(db, application_id=application_id)
    if not db_application:
        raise HTTPException(status_code=404, detail="Application not found")

    update_data = application.dict(exclude_unset=True)

    # Check if the domain exists when being updated
    if "domain_id" in update_data:
        domain = get_domain(db, domain_id=update_data["domain_id"])
        if not domain:
            raise HTTPException(status_code=404, detail="Domain not found")

    # Check for unique application name within the domain if being updated
    if "name" in update_data and update_data["name"] != db_application.name:
        domain_id = update_data.get("domain_id", db_application.domain_id)
        existing_apps = fetch_applications_by_domain_id(
            db, domain_id=domain_id, application_name=update_data["name"]
        )
        if existing_apps:
            raise HTTPException(status_code=400, detail="Application name already exists in this domain")

    # Encrypt sensitive fields if being updated
    if "config" in update_data and update_data["config"]:
        update_data["config"] = hybrid_encryption.encrypt_sensitive_field(update_data["config"])

    # Update the application fields
    for key, value in update_data.items():
        setattr(db_application, key, value)

    db.add(db_application)
    db.commit()
    db.refresh(db_application)
    return db_application


def delete_application(db: Session, application_id: uuid.UUID) -> None:
    """Delete an application"""
    db_application = get_application(db, application_id=application_id)
    if not db_application:
        raise HTTPException(status_code=404, detail="Application not found")
    
    db.delete(db_application)
    db.commit()
    return None
