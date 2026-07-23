from sqlalchemy.orm import Session
from typing import List, Optional

from app.domains.exceptions import (
    DomainNotFoundError,
    DuplicateDomainNameError,
    DuplicateDomainCodeError,
)

from uuid import UUID
from app.domains.models.domain import Domain
from app.domains.schemas.domain import DomainCreate, DomainUpdate
from app.core.hybrid_encryption import hybrid_encryption
from app.infrastructure.audit_tenant import fire_audit_log

def get_domain(db: Session, domain_id: int) -> Optional[Domain]:
    """Get a domain by ID"""
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if domain:
        _decrypt_domain_fields(domain)
    return domain

def _decrypt_domain_fields(domain: Domain) -> None:
    """Decrypt sensitive fields in domain object"""
    if domain.action:
        try:
            domain.action = hybrid_encryption.decrypt_sensitive_field(domain.action)
        except Exception:
            # If decryption fails, the field might not be encrypted (legacy data)
            pass

def get_domain_by_code(db: Session, domain_code: str) -> Optional[Domain]:
    """Get a domain by code"""
    domain = db.query(Domain).filter(Domain.domain_code == domain_code).first()
    if domain:
        _decrypt_domain_fields(domain)
    return domain

def get_domain_by_name(db: Session, domain_name: str) -> Optional[Domain]:
    """Get a domain by name"""
    domain = db.query(Domain).filter(Domain.domain_name == domain_name).first()
    if domain:
        _decrypt_domain_fields(domain)
    return domain

def get_domains(db: Session, skip: int = 0, limit: int = 100) -> List[Domain]:
    """Get all domains with pagination"""
    domains = db.query(Domain).offset(skip).limit(limit).all()
    for domain in domains:
        _decrypt_domain_fields(domain)
    return domains

def create_domain(db: Session, domain: DomainCreate, user_id: Optional[UUID] = None) -> Domain:
    """Create a new domain"""
    # Check if domain code already exists
    db_domain = get_domain_by_code(db, domain_code=domain.domain_code)
    if db_domain:
        raise DuplicateDomainCodeError()

    # Check if domain name already exists
    if get_domain_by_name(db, domain_name=domain.domain_name):
        raise DuplicateDomainNameError()

    # Encrypt sensitive fields
    encrypted_action = None
    if domain.action:
        encrypted_action = hybrid_encryption.encrypt_sensitive_field(domain.action)

    # Create new domain
    db_domain = Domain(
        domain_name=domain.domain_name,
        domain_code=domain.domain_code,
        description=domain.description,
        status=domain.status,
        action=encrypted_action
    )
    db.add(db_domain)
    db.commit()
    db.refresh(db_domain)
    fire_audit_log(
        action="CREATE", object_type="Domain",
        object_id=str(db_domain.id),
        user_id=str(user_id) if user_id else None,
        new_values={"domain_name": db_domain.domain_name, "domain_code": db_domain.domain_code},
    )
    return db_domain

def update_domain(db: Session, domain_id: int, domain: DomainUpdate, user_id: Optional[UUID] = None) -> Domain:
    """Update a domain"""
    db_domain = get_domain(db, domain_id=domain_id)
    if not db_domain:
        raise DomainNotFoundError()

    update_data = domain.dict(exclude_unset=True)

    # Check code uniqueness if being updated
    if "domain_code" in update_data and update_data["domain_code"] != db_domain.domain_code:
        if get_domain_by_code(db, domain_code=update_data["domain_code"]):
            raise DuplicateDomainCodeError()

    # Check name uniqueness if being updated
    if "domain_name" in update_data and update_data["domain_name"] != db_domain.domain_name:
        if get_domain_by_name(db, domain_name=update_data["domain_name"]):
            raise DuplicateDomainNameError()

    # Encrypt sensitive fields if being updated
    if "action" in update_data and update_data["action"]:
        update_data["action"] = hybrid_encryption.encrypt_sensitive_field(update_data["action"])

    for key, value in update_data.items():
        setattr(db_domain, key, value)

    db.add(db_domain)
    db.commit()
    db.refresh(db_domain)
    fire_audit_log(
        action="UPDATE", object_type="Domain",
        object_id=str(domain_id),
        user_id=str(user_id) if user_id else None,
        new_values=update_data,
    )
    return db_domain

def delete_domain(db: Session, domain_id: int, user_id: Optional[UUID] = None) -> None:
    """Delete a domain"""
    db_domain = get_domain(db, domain_id=domain_id)
    if not db_domain:
        raise DomainNotFoundError()
    
    db.delete(db_domain)
    db.commit()
    fire_audit_log(
        action="DELETE", object_type="Domain",
        object_id=str(domain_id),
        user_id=str(user_id) if user_id else None,
    )
    return None
