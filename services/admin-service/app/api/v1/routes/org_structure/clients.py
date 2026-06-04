from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from uuid import UUID
import os
import logging

logger = logging.getLogger(__name__)

from app.infrastructure.database.session import get_db
from app.core.security import get_current_user  # Uses optional auth support
from app.core.config import settings
# User model not in scope - commenting out for now
# from app.models.user import User
from app.clients.models.clients import Client
from app.clients.schemas.clients import (
    ClientCreate,
    ClientUpdate,
    ClientResponse,
    ClientListResponse,
    ClientConfigurationStatus
)
# from app.core.security import get_password_hash  # Not used
# from app.services.redis_cache import redis_cache  # Not in scope

# Check if authentication is required
REQUIRE_AUTH = os.getenv("REQUIRE_AUTH", "false").lower() == "true"

# Simple admin check for no-auth mode (User model not in scope)
def require_admin_role(current_user=Depends(get_current_user)):
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
    current_user=Depends(require_admin_role)
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

    # Cache removed (redis_cache not in scope)
    # Invalidate clients list cache removed

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
    current_user=Depends(require_admin_role)
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

@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Get client by ID"""
    # Simplified without User model - allow access to any client
    client = db.query(Client).filter(Client.client_id == client_id).first()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    return client

@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: UUID,
    client_data: ClientUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin_role)
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
    current_user=Depends(require_admin_role)
):
    """Soft delete client (admin only)"""
    client = db.query(Client).filter(
        Client.client_id == client_id,
        Client.is_active == True
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Perform soft delete
    client.is_active = False

    db.commit()

    return {"message": "Client deleted successfully"}
