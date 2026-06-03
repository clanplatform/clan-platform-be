from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List, Optional

from app.models.domain import Domain
from app.schemas.domain import DomainCreate, DomainUpdate
from app.core.hybrid_encryption import hybrid_encryption

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

def create_domain(db: Session, domain: DomainCreate) -> Domain:
    """Create a new domain"""
    # Check if domain code already exists
    db_domain = get_domain_by_code(db, domain_code=domain.domain_code)
    if db_domain:
        raise HTTPException(status_code=400, detail="Domain code already registered")

    # Check if domain name already exists
    if get_domain_by_name(db, domain_name=domain.domain_name):
        raise HTTPException(status_code=400, detail="Domain name already registered")

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
    return db_domain

def update_domain(db: Session, domain_id: int, domain: DomainUpdate) -> Domain:
    """Update a domain"""
    db_domain = get_domain(db, domain_id=domain_id)
    if not db_domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    update_data = domain.dict(exclude_unset=True)

    # Check code uniqueness if being updated
    if "domain_code" in update_data and update_data["domain_code"] != db_domain.domain_code:
        if get_domain_by_code(db, domain_code=update_data["domain_code"]):
            raise HTTPException(status_code=400, detail="Domain code already registered")

    # Check name uniqueness if being updated
    if "domain_name" in update_data and update_data["domain_name"] != db_domain.domain_name:
        if get_domain_by_name(db, domain_name=update_data["domain_name"]):
            raise HTTPException(status_code=400, detail="Domain name already registered")

    # Encrypt sensitive fields if being updated
    if "action" in update_data and update_data["action"]:
        update_data["action"] = hybrid_encryption.encrypt_sensitive_field(update_data["action"])

    for key, value in update_data.items():
        setattr(db_domain, key, value)

    db.add(db_domain)
    db.commit()
    db.refresh(db_domain)
    return db_domain

def delete_domain(db: Session, domain_id: int) -> None:
    """Delete a domain"""
    db_domain = get_domain(db, domain_id=domain_id)
    if not db_domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    
    db.delete(db_domain)
    db.commit()
    return None
