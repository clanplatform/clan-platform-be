from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from uuid import UUID
import os
import logging

logger = logging.getLogger(__name__)

from app.db.database import get_db
from app.core.security import get_current_user  # Uses optional auth support
from app.core.config import settings
from app.models.user import User
from app.models.client import Client
from app.schemas.client import (
    ClientCreate,
    ClientUpdate,
    ClientResponse,
    ClientListResponse,
    ClientConfigurationStatus
)
from app.core.security import get_password_hash
from app.services.redis_cache import redis_cache

# Check if authentication is required
REQUIRE_AUTH = os.getenv("REQUIRE_AUTH", "false").lower() == "true"

# Simple admin check for no-auth mode
def require_admin_role(current_user: User = Depends(get_current_user)) -> User:
    """Require admin role (bypassed when REQUIRE_AUTH=false)"""
    if not REQUIRE_AUTH:
        return current_user  # Skip role check in no-auth mode
    # In auth mode, you would check roles here
    return current_user

router = APIRouter()

@router.post("/", response_model=ClientResponse)
async def create_client(
    client_data: ClientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_role)
):
    """Create a new client (admin only)"""
    # Check if client with same client_name already exists
    existing_client = db.query(Client).filter(Client.client_name == client_data.client_name).first()
    if existing_client:
        raise HTTPException(status_code=400, detail="Client with this name already exists")

    # Check if email already exists
    existing_email = db.query(Client).filter(Client.contact_email == client_data.contact_email).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Client email already exists")

    # Create new client using model_dump to get all fields
    db_client = Client(**client_data.model_dump())

    db.add(db_client)
    db.commit()
    db.refresh(db_client)

    # Cache the created client
    client_dict = {
        "client_id": str(db_client.client_id),
        "client_name": db_client.client_name,
        "contact_email": db_client.contact_email,
        "created_at": str(db_client.created_at),
        "updated_at": str(db_client.updated_at)
    }
    redis_cache.cache_client(str(db_client.client_id), client_dict, ttl=settings.CACHE_DEFAULT_TTL)

    # Invalidate clients list cache
    redis_cache.delete_pattern("clients:list:*")

    return db_client

@router.get("/", response_model=ClientListResponse)
async def list_clients(
    response: Response,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    subscription_plan: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    onboarding_status: Optional[str] = Query(None),
    _t: Optional[str] = Query(None),  # Cache-busting parameter (ignored)
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_role)
):
    """List all clients with pagination and filtering (admin only)"""
    # Add cache control headers to prevent browser caching
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    query = db.query(Client)

    # Apply filters
    if search:
        query = query.filter(Client.client_name.ilike(f"%{search}%"))
    
    # Get total count
    total = query.count()
    
    # Apply FILO sorting (newest first) before pagination
    query = query.order_by(Client.created_at.desc())
    
    # Apply pagination
    clients = query.offset((page - 1) * size).limit(size).all()
    
    return ClientListResponse(
        clients=clients,
        total=total,
        page=page,
        page_size=size,
        total_pages=(total + size - 1) // size
    )

@router.get("/me", response_model=ClientResponse)
async def get_my_client(
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get current user's client information"""
    # Add cache control headers to prevent browser caching
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    
    client = db.query(Client).filter(Client.client_id == current_user.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    return client

@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get client by ID"""
    logger.info(f"GET /clients/{client_id} - User: {current_user.email}, Is Admin: {current_user.is_admin()}")
    logger.info(f"User client_id: {current_user.client_id}")

    # Admin can access any client, regular users only their own
    if current_user.is_admin():
        client = db.query(Client).filter(
            Client.client_id == client_id
        ).first()
    else:
        # Check if user has a client_id
        user_client_id = current_user.client_id
        if user_client_id is None:
            raise HTTPException(
                status_code=403, 
                detail="User is not associated with any client"
            )
        
        client = db.query(Client).filter(
            Client.client_id == client_id,
            Client.client_id == user_client_id
        ).first()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    return client

@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: UUID,
    client_data: ClientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_role)
):
    """Update client (admin only)"""
    client = db.query(Client).filter(Client.client_id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Update fields
    update_data = client_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(client, field, value)

    db.commit()
    db.refresh(client)

    return client

@router.delete("/{client_id}")
async def delete_client(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_role)
):
    """Soft delete client (admin only)"""
    client = db.query(Client).filter(
        Client.client_id == client_id,
        Client.is_active_client == True
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Perform soft delete
    client.is_active_client = False
    client.active = False
    client.deleted = True

    db.commit()

    return {"message": "Client deleted successfully"}

@router.get("/{client_id}/configuration-status", response_model=ClientConfigurationStatus)
async def get_client_configuration_status(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get client configuration status including entity setup"""
    client = db.query(Client).filter(Client.client_id == client_id).first()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Check if user has access to this client
    if not current_user.is_admin() and current_user.client_id != client_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Check entity configuration
    from app.models.entity import Entity
    from app.models.department import Department
    from app.models.division import Division
    from app.models.job_code import JobCodeBasicInfo

    entities_count = db.query(Entity).filter(Entity.client_id == client_id).count()
    departments_count = db.query(Department).filter(Department.client_id == client_id).count()
    divisions_count = db.query(Division).filter(Division.client_id == client_id).count()
    # Count job codes by basic info records tied to client_id
    job_codes_count = db.query(JobCodeBasicInfo).filter(JobCodeBasicInfo.client_id == client_id).count()
    users_count = db.query(User).filter(User.client_id == client_id).count()

    # Determine setup status
    has_entities = entities_count > 0
    has_organizational_structure = departments_count > 0 or divisions_count > 0
    has_job_codes = job_codes_count > 0
    has_users = users_count > 1  # More than just the admin user

    setup_completion = 0
    if has_entities:
        setup_completion += 25
    if has_organizational_structure:
        setup_completion += 25
    if has_job_codes:
        setup_completion += 25
    if has_users:
        setup_completion += 25

    return ClientConfigurationStatus(
        client_id=client_id,
        has_entities=has_entities,
        entities_count=entities_count,
        has_organizational_structure=has_organizational_structure,
        departments_count=departments_count,
        divisions_count=divisions_count,
        has_job_codes=has_job_codes,
        job_codes_count=job_codes_count,
        has_users=has_users,
        users_count=users_count,
        setup_completion_percentage=setup_completion,
        recommended_next_steps=_get_recommended_next_steps(
            has_entities, has_organizational_structure, has_job_codes, has_users
        )
    )



def _get_recommended_next_steps(
    has_entities: bool,
    has_organizational_structure: bool,
    has_job_codes: bool,
    has_users: bool
) -> List[str]:
    """Get recommended next steps based on current configuration"""
    steps = []
    
    if not has_entities:
        steps.append("Create your first entity (headquarters, main office, or primary location)")
    elif not has_organizational_structure:
        steps.append("Set up departments and divisions within your entities")
    elif not has_job_codes:
        steps.append("Define job codes and roles for your organization")
    elif not has_users:
        steps.append("Invite team members and assign them to appropriate roles")
    else:
        steps.append("Your basic setup is complete! Consider adding more entities or refining your organizational structure")
    
    return steps
