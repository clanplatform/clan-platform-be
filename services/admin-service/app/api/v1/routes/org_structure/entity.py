from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from uuid import UUID
import os

from app.infrastructure.database.session import get_db, get_tenant_db
from app.core.security import get_current_user
from app.entities.models.entity import Entity
from app.entities.schemas.entity import (
    EntityCreate,
    EntityUpdate,
    EntityResponse,
    EntityListResponse
)
from app.infrastructure.audit_helpers import RISK_SCORE, get_client_ip, get_audit_org_context, get_user_id, get_session_id
from app.infrastructure.audit_tenant import fire_audit_log

REQUIRE_AUTH = os.getenv("REQUIRE_AUTH", "false").lower() == "true"

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
        db_entity = Entity(**entity.model_dump())
        db.add(db_entity)
        db.commit()
        db.refresh(db_entity)

        try:
            tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="CREATE",
                object_type="Entity",
                object_id=str(db_entity.entity_id),
                user_id=get_user_id(current_user),
                tenant_id=tenant_id_audit,
                entity_id=entity_id_audit,
                session_id=get_session_id(current_user),
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                risk_score=RISK_SCORE["CREATE"],
                new_values={
                    "entity_name": db_entity.entity_name,
                    "entity_code": db_entity.entity_code,
                    "tenant_id": str(db_entity.tenant_id),
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
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=EntityListResponse)
async def list_entities(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    tenant_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_tenant_db),
    current_user=Depends(get_current_user)
):
    """List all entities with pagination and filtering"""
    query = db.query(Entity).filter(Entity.active == True)

    if tenant_id:
        query = query.filter(Entity.tenant_id == tenant_id)
    if search:
        query = query.filter(Entity.entity_name.ilike(f"%{search}%"))

    total = query.count()
    query = query.order_by(Entity.created_at.desc())
    entities = query.offset((page - 1) * size).limit(size).all()

    try:
        tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="READ",
            object_type="Entity",
            user_id=get_user_id(current_user),
            tenant_id=tenant_id_audit,
            entity_id=entity_id_audit,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score="LOW",
        )
    except Exception:
        pass

    return EntityListResponse(
        entities=entities,
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size
    )


@router.get("/{entity_id}", response_model=EntityResponse)
async def get_entity(
    request: Request,
    entity_id: UUID,
    db: Session = Depends(get_tenant_db),
    current_user=Depends(get_current_user)
):
    """Get entity by ID"""
    entity = db.query(Entity).filter(
        Entity.entity_id == entity_id,
        Entity.active == True
    ).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    try:
        tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="READ",
            object_type="Entity",
            object_id=str(entity_id),
            user_id=get_user_id(current_user),
            tenant_id=tenant_id_audit,
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
    current_user=Depends(get_current_user)
):
    """Update entity"""
    entity = db.query(Entity).filter(Entity.entity_id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    old_values = {
        "entity_name": entity.entity_name,
        "entity_code": entity.entity_code,
        "tenant_id": str(entity.tenant_id),
    }

    update_data = entity_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(entity, field, value)

    db.commit()
    db.refresh(entity)

    try:
        tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="UPDATE",
            object_type="Entity",
            object_id=str(entity_id),
            user_id=get_user_id(current_user),
            tenant_id=tenant_id_audit,
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
    current_user=Depends(get_current_user)
):
    """Soft delete entity"""
    entity = db.query(Entity).filter(
        Entity.entity_id == entity_id,
        Entity.active == True
    ).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    old_entity_name = entity.entity_name
    entity.active = False
    db.commit()

    try:
        tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="DELETE",
            object_type="Entity",
            object_id=str(entity_id),
            user_id=get_user_id(current_user),
            tenant_id=tenant_id_audit,
            entity_id=entity_id_audit,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score=RISK_SCORE["DELETE"],
            old_values={"entity_name": old_entity_name, "id": str(entity_id)},
        )
    except Exception:
        pass

    return {"message": "Entity deleted successfully"}
