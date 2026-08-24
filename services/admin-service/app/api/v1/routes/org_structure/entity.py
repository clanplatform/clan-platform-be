from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from uuid import UUID
import os

from app.infrastructure.database.session import get_db, get_tenant_db
from app.core.security import get_current_user
from app.entities.models.entity import Entity
from app.entities.services import entity as entity_service
from app.entities.exceptions import EntityNotFoundError
from app.entities.schemas.entity import (
    EntityCreate,
    EntityUpdate,
    EntityResponse,
    EntityListResponse
)
from app.infrastructure.audit_helpers import RISK_SCORE, get_client_ip, get_audit_org_context, get_user_id, get_session_id
from app.infrastructure.audit_tenant import fire_audit_log
from app.infrastructure.scope_helpers import resolve_scope_filter, scoped_entity_ids, require_whole_org_admin

REQUIRE_AUTH = os.getenv("REQUIRE_AUTH", "false").lower() == "true"

router = APIRouter()


@router.post("/", response_model=EntityResponse)
async def create_entity(
    request: Request,
    entity: EntityCreate,
    db: Session = Depends(get_tenant_db),
    current_user=Depends(require_whole_org_admin)
):
    """Create a new entity.

    Restricted to a role with is_admin=True AND access_scope=
    'whole_organization' — see require_whole_org_admin.
    """
    # tenant_id is taken from the JWT, never the body. None => master-DB user.
    tenant_id = current_user.get("tenant_id") if isinstance(current_user, dict) else None
    try:
        # Delegate to the service layer: duplicate entity_code check and
        # autogeneration of the locale fields from country_code. tenant_id is
        # supplied from the token, not the payload.
        db_entity = entity_service.create_entity(
            db, entity, tenant_id=tenant_id, user_id=get_user_id(current_user)
        )

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
                    "tenant_id": str(db_entity.tenant_id) if db_entity.tenant_id else None,
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
    db: Session = Depends(get_tenant_db),
    current_user=Depends(get_current_user)
):
    """List all entities with pagination and filtering"""
    query = db.query(Entity).filter(Entity.active == True)

    scope_filter = resolve_scope_filter(db, get_user_id(current_user))
    ids = scoped_entity_ids(db, scope_filter)
    if ids is not None:
        query = query.filter(Entity.entity_id.in_(ids))

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
        raise EntityNotFoundError()

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
    current_user=Depends(require_whole_org_admin)
):
    """Update entity"""
    entity = db.query(Entity).filter(Entity.entity_id == entity_id).first()
    if not entity:
        raise EntityNotFoundError()

    old_values = {
        "entity_name": entity.entity_name,
        "entity_code": entity.entity_code,
        "tenant_id": str(entity.tenant_id),
    }

    update_data = entity_data.model_dump(exclude_unset=True)

    # Delegate to the service layer: entity_code uniqueness check and
    # regeneration of the locale fields when country_code changes.
    entity = entity_service.update_entity(
        db, entity_id, entity_data, user_id=get_user_id(current_user)
    )

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
    current_user=Depends(require_whole_org_admin)
):
    """Soft delete entity"""
    entity = db.query(Entity).filter(
        Entity.entity_id == entity_id,
        Entity.active == True
    ).first()
    if not entity:
        raise EntityNotFoundError()

    old_entity_name = entity.entity_name
    # Delegate to the service layer (sets deleted=True and active=False)
    if not entity_service.delete_entity(db, entity_id, user_id=get_user_id(current_user)):
        raise EntityNotFoundError()

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
