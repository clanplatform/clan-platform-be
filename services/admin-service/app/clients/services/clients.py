from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from uuid import UUID

from app.models.client import Client, ClientApplication
from app.models.domain import DomainApplication
from app.schemas.client import ClientCreate, ClientUpdate, ClientApplicationCreate, ClientApplicationUpdate, DomainApplicationCreate, DomainApplicationUpdate
from app.core.hybrid_encryption import hybrid_encryption

# Client CRUD operations
def get_client(db: Session, client_id: UUID) -> Optional[Client]:
    """Get a client by ID"""
    client = db.query(Client).filter(Client.client_id == client_id).first()
    return client

def get_client_by_email(db: Session, email: str) -> Optional[Client]:
    """Get a client by email"""
    return db.query(Client).filter(Client.email == email).first()

def get_client_by_company_name(db: Session, company_name: str) -> Optional[Client]:
    """Get a client by company name"""
    return db.query(Client).filter(Client.company_name == company_name).first()

def get_clients(db: Session, skip: int = 0, limit: int = 100, active_only: bool = True) -> List[Client]:
    """Get multiple clients with pagination"""
    query = db.query(Client)
    
    if active_only:
        query = query.filter(Client.active == "true", Client.deleted == "N")
    
    clients = query.offset(skip).limit(limit).all()
    
    return clients

def get_clients_by_domain(db: Session, domain_id: int, skip: int = 0, limit: int = 100) -> List[Client]:
    """Get clients by domain ID"""
    # Note: Client model doesn't have domain_id field directly
    # This function needs to be updated to use the relationship through domains
    clients = db.query(Client).join(Client.domains).filter(
        Client.domains.any(domain_id=domain_id),
        Client.active == "true",
        Client.deleted == "N"
    ).offset(skip).limit(limit).all()
    
    return clients

def create_client(db: Session, client: ClientCreate) -> Client:
    """Create a new client"""
    # Check if client with same email already exists
    existing_client = get_client_by_email(db, client.email)
    if existing_client:
        raise ValueError(f"Client with email {client.email} already exists")
    
    # Check if client with same company name already exists
    existing_company = get_client_by_company_name(db, client.company_name)
    if existing_company:
        raise ValueError(f"Client with company name {client.company_name} already exists")
    
    db_client = Client(**client.model_dump())
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client

def update_client(db: Session, client_id: UUID, client_update: ClientUpdate) -> Optional[Client]:
    """Update an existing client"""
    db_client = get_client(db, client_id)
    if not db_client:
        return None
    
    # Check for email uniqueness if email is being updated
    if client_update.email and client_update.email != db_client.email:
        existing_client = get_client_by_email(db, client_update.email)
        if existing_client and existing_client.client_id != client_id:
            raise ValueError(f"Client with email {client_update.email} already exists")
    
    # Check for company name uniqueness if company name is being updated
    if client_update.company_name and client_update.company_name != db_client.company_name:
        existing_company = get_client_by_company_name(db, client_update.company_name)
        if existing_company and existing_company.client_id != client_id:
            raise ValueError(f"Client with company name {client_update.company_name} already exists")
    
    # Update fields
    update_data = client_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_client, field, value)
    
    db.commit()
    db.refresh(db_client)
    return db_client

def delete_client(db: Session, client_id: UUID) -> bool:
    """Soft delete a client (mark as deleted)"""
    db_client = get_client(db, client_id)
    if not db_client:
        return False
    
    db_client.deleted = "Y"
    db_client.active = "false"
    db.commit()
    return True

def hard_delete_client(db: Session, client_id: UUID) -> bool:
    """Hard delete a client (permanently remove from database)"""
    db_client = get_client(db, client_id)
    if not db_client:
        return False
    
    db.delete(db_client)
    db.commit()
    return True

# Client Application CRUD operations
def get_client_application(db: Session, client_id: UUID, app_id: int) -> Optional[ClientApplication]:
    """Get a client-application mapping"""
    return db.query(ClientApplication).filter(
        ClientApplication.client_id == client_id,
        ClientApplication.app_id == app_id
    ).first()

def get_client_applications(db: Session, client_id: UUID) -> List[ClientApplication]:
    """Get all applications for a client"""
    return db.query(ClientApplication).filter(
        ClientApplication.client_id == client_id
    ).all()

def get_application_clients(db: Session, app_id: int) -> List[ClientApplication]:
    """Get all clients for an application"""
    return db.query(ClientApplication).filter(
        ClientApplication.app_id == app_id
    ).all()

def create_client_application(db: Session, client_app: ClientApplicationCreate) -> ClientApplication:
    """Create a new client-application mapping"""
    # Check if mapping already exists
    existing_mapping = get_client_application(db, client_app.client_id, client_app.app_id)
    if existing_mapping:
        raise ValueError(f"Client-Application mapping already exists for client {client_app.client_id} and app {client_app.app_id}")
    
    db_client_app = ClientApplication(**client_app.model_dump())
    db.add(db_client_app)
    db.commit()
    db.refresh(db_client_app)
    return db_client_app

def update_client_application(db: Session, client_id: UUID, app_id: int, client_app_update: ClientApplicationUpdate) -> Optional[ClientApplication]:
    """Update a client-application mapping"""
    db_client_app = get_client_application(db, client_id, app_id)
    if not db_client_app:
        return None
    
    update_data = client_app_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_client_app, field, value)
    
    db.commit()
    db.refresh(db_client_app)
    return db_client_app

def delete_client_application(db: Session, client_id: UUID, app_id: int) -> bool:
    """Delete a client-application mapping"""
    db_client_app = get_client_application(db, client_id, app_id)
    if not db_client_app:
        return False
    
    db.delete(db_client_app)
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
    # Check if mapping already exists
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
def get_client_hierarchy(db: Session, client_id: UUID) -> dict:
    """Get complete hierarchy for a client: Client -> Domains -> Applications"""
    client = get_client(db, client_id)
    if not client:
        return None
    
    # Get client's domains
    domains = get_clients_by_domain(db, client.domain_id) if client.domain_id else []
    
    # Get applications for each domain
    hierarchy = {
        "client": client,
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
    """Get complete hierarchy for a domain: Domain -> Applications -> Clients"""
    from app.crud.domain import get_domain
    
    domain = get_domain(db, domain_id)
    if not domain:
        return None
    
    # Get domain's applications
    domain_apps = get_domain_applications(db, domain_id)
    
    # Get clients for this domain
    clients = get_clients_by_domain(db, domain_id)
    
    hierarchy = {
        "domain": domain,
        "applications": domain_apps,
        "clients": clients
    }
    
    return hierarchy