from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from uuid import UUID
import os

from app.infrastructure.database.session import get_db, get_tenant_db
from app.core.security import get_current_user  # Uses optional auth support
from app.entities.models.entity import Entity
from app.tenants.models.tenants import Tenant
from app.entities.schemas.entity import (
    EntityCreate,
    EntityUpdate,
    EntityResponse,
    EntityListResponse
)
from app.infrastructure.audit_helpers import RISK_SCORE, get_client_ip, get_audit_org_context, get_user_id, get_session_id
from app.infrastructure.audit_client import fire_audit_log

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

@router.post("/", response_model=EntityResponse)
async def create_entity(
    request: Request,
    entity: EntityCreate,
    db: Session = Depends(get_tenant_db),
    current_user=Depends(get_current_user)
):
    """Create a new entity"""
    try:
        # Validate client exists
        client = db.query(Client).filter(Client.client_id == entity.client_id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        # Create entity
        db_entity = Entity(**entity.model_dump())
        db.add(db_entity)
        db.commit()
        db.refresh(db_entity)

        # Audit log: entity created
        try:
            client_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="CREATE",
                object_type="Entity",
                object_id=str(db_entity.entity_id),
                user_id=get_user_id(current_user),
                client_id=client_id_audit,
                entity_id=entity_id_audit,
                session_id=get_session_id(current_user),
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                risk_score=RISK_SCORE["CREATE"],
                new_values={
                    "name": db_entity.name,
                    "client_id": str(db_entity.client_id),
                    "entity_type": db_entity.entity_type,
                },
            )
        except Exception:
            pass

        return db_entity
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        import traceback
        error_detail = f"{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        print(f"ERROR creating entity: {error_detail}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=EntityListResponse)
async def list_entities(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    client_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_tenant_db),
    current_user = Depends(get_current_user)
):
    """List all entities with pagination and filtering"""
    query = db.query(Entity).filter(
        Entity.active == True
    )

    # Apply client filter based on user permissions
    # In no-auth mode, show all entities
    if not REQUIRE_AUTH:
        if client_id:
            query = query.filter(Entity.client_id == client_id)
    elif hasattr(current_user, 'is_admin') and callable(current_user.is_admin) and current_user.is_admin():
        if client_id:
            query = query.filter(Entity.client_id == client_id)
    else:
        # Regular users can only see entities from their client
        if hasattr(current_user, 'client_id') and current_user.client_id:
            query = query.filter(Entity.client_id == current_user.client_id)
    
    # Apply other filters
    if entity_type:
        query = query.filter(Entity.entity_type == entity_type)
    if search:
        query = query.filter(Entity.name.ilike(f"%{search}%"))
    
    # Get total count
    total = query.count()
    
    # Sort by created_at in descending order (newest first - FILO)
    query = query.order_by(Entity.created_at.desc())
    
    # Apply pagination
    entities = query.offset((page - 1) * size).limit(size).all()
    
    result = EntityListResponse(
        entities=entities,
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size
    )
    try:
        client_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="READ",
            object_type="Entity",
            user_id=get_user_id(current_user),
            client_id=client_id_audit,
            entity_id=entity_id_audit,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score="LOW",
        )
    except Exception:
        pass
    return result

@router.get("/{entity_id}", response_model=EntityResponse)
async def get_entity(
    request: Request,
    entity_id: UUID,
    db: Session = Depends(get_tenant_db),
    current_user = Depends(get_current_user)
):
    """Get entity by ID"""
    query = db.query(Entity).filter(
        Entity.entity_id == entity_id,
        Entity.active == True
    )
    
    # Apply client filter for non-admin users
    if not current_user.is_admin():
        user_client_id = current_user.client_id
        if user_client_id is None:
            raise HTTPException(
                status_code=403,
                detail="User is not associated with any client"
            )
        query = query.filter(Entity.client_id == user_client_id)
    
    entity = query.first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    try:
        client_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="READ",
            object_type="Entity",
            object_id=str(entity_id),
            user_id=get_user_id(current_user),
            client_id=client_id_audit,
            entity_id=entity_id_audit,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score="LOW",
        )
    except Exception:
        pass
    return entity

@router.put("/{entity_id}", response_model=EntityResponse)
async def update_entity(
    request: Request,
    entity_id: UUID,
    entity_data: EntityUpdate,
    db: Session = Depends(get_tenant_db),
    current_user = Depends(get_current_user)
):
    """Update entity"""
    query = db.query(Entity).filter(Entity.entity_id == entity_id)

    # Apply client filter for non-admin users
    if not current_user.is_admin():
        user_client_id = current_user.client_id
        if user_client_id is None:
            raise HTTPException(
                status_code=403,
                detail="User is not associated with any client"
            )
        query = query.filter(Entity.client_id == user_client_id)

    entity = query.first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    # Capture old values before update for audit
    old_values = {
        "name": entity.name,
        "client_id": str(entity.client_id),
        "entity_type": entity.entity_type,
    }

    # Update fields
    update_data = entity_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(entity, field, value)

    db.commit()
    db.refresh(entity)

    # Audit log: entity updated
    try:
        client_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="UPDATE",
            object_type="Entity",
            object_id=str(entity_id),
            user_id=get_user_id(current_user),
            client_id=client_id_audit,
            entity_id=entity_id_audit,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score=RISK_SCORE["UPDATE"],
            old_values=old_values,
            new_values=update_data,
        )
    except Exception:
        pass

    return entity

@router.delete("/{entity_id}")
async def delete_entity(
    request: Request,
    entity_id: UUID,
    db: Session = Depends(get_tenant_db),
    current_user = Depends(get_current_user)
):
    """Soft delete entity"""
    query = db.query(Entity).filter(
        Entity.entity_id == entity_id,
        Entity.active == True
    )

    # Apply client filter for non-admin users
    if not current_user.is_admin():
        user_client_id = current_user.client_id
        if user_client_id is None:
            raise HTTPException(
                status_code=403,
                detail="User is not associated with any client"
            )
        query = query.filter(Entity.client_id == user_client_id)

    entity = query.first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    # Check if entity has active child entities
    child_entities = db.query(Entity).filter(
        Entity.parent_entity_id == entity_id,
        Entity.active == True
    ).count()
    if child_entities > 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete entity with active child entities"
        )

    # Snapshot name before soft delete for audit
    old_entity_name = entity.name

    # Perform soft delete
    entity.active = False

    db.commit()

    # Audit log: entity deleted
    try:
        client_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="DELETE",
            object_type="Entity",
            object_id=str(entity_id),
            user_id=get_user_id(current_user),
            client_id=client_id_audit,
            entity_id=entity_id_audit,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score=RISK_SCORE["DELETE"],
            old_values={"name": old_entity_name, "id": str(entity_id)},
        )
    except Exception:
        pass

    return {"message": "Entity deleted successfully"}

# @router.get("/by-client/{client_id}", response_model=EntityListResponse)
# async def get_entities_by_client(
#     client_id: UUID,
#     page: int = Query(1, ge=1),
#     size: int = Query(10, ge=1, le=100),
#     entity_type: Optional[str] = Query(None),
#     include_inactive: bool = Query(False),
#     db: Session = Depends(get_tenant_db),
#     current_user = Depends(get_current_user)
# ):
#     """Get all entities for a specific client"""
#     # Check if client exists
#     client = db.query(Client).filter(Client.client_id == client_id).first()
#     if not client:
#         raise HTTPException(status_code=404, detail="Client not found")
    
#     # Check permissions - admin can access any client, users only their own
#     user_client_id = current_user.client_id
#     if not current_user.is_admin() and user_client_id != client_id:
#         raise HTTPException(status_code=403, detail="Not authorized to access this client's entities")
    
#     # Build query
#     query = db.query(Entity).filter(
#         Entity.client_id == client_id
#     )
    
#     # Apply filters
#     if entity_type:
#         query = query.filter(Entity.entity_type == entity_type)
#     if not include_inactive:
#         query = query.filter(Entity.active == True)
    
#     # Get total count
#     total = query.count()
    
#     # Sort by created_at in descending order (newest first - FILO)
#     query = query.order_by(Entity.created_at.desc())
    
#     # Apply pagination
#     entities = query.offset((page - 1) * size).limit(size).all()
    
#     return EntityListResponse(
#         entities=entities,
#         total=total,
#         page=page,
#         size=size,
#         pages=(total + size - 1) // size
#     )

# @router.get("/hierarchy/{client_id}")
# async def get_entity_hierarchy(
#     client_id: UUID,
#     db: Session = Depends(get_tenant_db),
#     current_user = Depends(get_current_user)
# ):
    """Get list of entities for a specific client"""
    # Check if client exists
    client = db.query(Client).filter(Client.client_id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Check permissions
    user_client_id = current_user.client_id
    if not current_user.is_admin() and user_client_id != client_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this client's entities")

    # Get all entities for the client
    entities = db.query(Entity).filter(
        Entity.client_id == client_id,
        Entity.active == True
    ).all()

    entity_list = [
        {
            "entity_id": entity.entity_id,
            "entity_name": entity.entity_name,
            "entity_code": entity.entity_code,
            "description": entity.description,
            "active": entity.active
        }
        for entity in entities
    ]

    return {
        "client_id": client_id,
        "client_name": client.company_name,
        "total_entities": len(entities),
        "entities": entity_list
    }