from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List, Optional
from uuid import UUID

from app.entities.models.entity import Entity
from app.entities.schemas.entity import EntityCreate, EntityUpdate
from app.core.hybrid_encryption import hybrid_encryption
from app.infrastructure.audit_client import fire_audit_log

def get_entity(db: Session, entity_id: int) -> Optional[Entity]:
    """Get an entity by ID"""
    entity = db.query(Entity).filter(Entity.entity_id == entity_id, Entity.deleted == False).first()
    if entity:
        _decrypt_entity_fields(entity)
    return entity

def _decrypt_entity_fields(entity: Entity) -> None:
    """Decrypt sensitive fields in entity object"""
    # Add decryption for sensitive fields if needed
    pass

def get_entity_by_code(db: Session, entity_code: str) -> Optional[Entity]:
    """Get an entity by code"""
    entity = db.query(Entity).filter(Entity.entity_code == entity_code, Entity.deleted == False).first()
    if entity:
        _decrypt_entity_fields(entity)
    return entity

def get_entities_by_client(db: Session, client_id: UUID, skip: int = 0, limit: int = 100) -> List[Entity]:
    """Get all entities for a specific client"""
    entities = db.query(Entity).filter(
        Entity.client_id == client_id,
        Entity.deleted == False
    ).offset(skip).limit(limit).all()
    
    for entity in entities:
        _decrypt_entity_fields(entity)
    return entities

def get_entities(db: Session, skip: int = 0, limit: int = 100) -> List[Entity]:
    """Get all entities with pagination"""
    entities = db.query(Entity).filter(Entity.deleted == False).offset(skip).limit(limit).all()
    for entity in entities:
        _decrypt_entity_fields(entity)
    return entities

def create_entity(db: Session, entity: EntityCreate, user_id: Optional[UUID] = None) -> Entity:
    """Create a new entity"""
    # Check if entity code already exists
    db_entity = get_entity_by_code(db, entity_code=entity.entity_code)
    if db_entity:
        raise HTTPException(status_code=400, detail="Entity code already registered")

    # Verify client exists
    from app.clients.services.clients import get_client
    client = get_client(db, entity.client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Create new entity
    entity_data = entity.model_dump()
    # Create entity without updated_at to avoid constraint issues
    db_entity = Entity(
        entity_name=entity_data['entity_name'],
        entity_code=entity_data['entity_code'],
        description=entity_data.get('description'),
        contact=entity_data.get('contact'),
        email=entity_data.get('email'),
        client_id=entity_data['client_id'],
        address_1=entity_data.get('address_1'),
        address_2=entity_data.get('address_2'),
        city_code=entity_data.get('city_code'),
        state_code=entity_data.get('state_code'),
        country_code=entity_data.get('country_code'),
        time_zone=entity_data.get('time_zone'),
        time_zone_offset=entity_data.get('time_zone_offset'),
        date_format=entity_data.get('date_format'),
        time_format=entity_data.get('time_format'),
        date_time_format=entity_data.get('date_time_format')
    )
    db.add(db_entity)
    db.commit()
    db.refresh(db_entity)
    fire_audit_log(
        action="CREATE", object_type="Entity",
        object_id=str(db_entity.entity_id),
        client_id=str(db_entity.client_id),
        user_id=str(user_id) if user_id else None,
        new_values={"entity_name": db_entity.entity_name, "entity_code": db_entity.entity_code},
    )
    return db_entity

def update_entity(db: Session, entity_id: int, entity: EntityUpdate, user_id: Optional[UUID] = None) -> Optional[Entity]:
    """Update an entity"""
    db_entity = get_entity(db, entity_id=entity_id)
    if not db_entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    update_data = entity.model_dump(exclude_unset=True)

    # Check code uniqueness if being updated
    if "entity_code" in update_data and update_data["entity_code"] != db_entity.entity_code:
        if get_entity_by_code(db, entity_code=update_data["entity_code"]):
            raise HTTPException(status_code=400, detail="Entity code already registered")

    for key, value in update_data.items():
        setattr(db_entity, key, value)

    db.add(db_entity)
    db.commit()
    db.refresh(db_entity)
    fire_audit_log(
        action="UPDATE", object_type="Entity",
        object_id=str(entity_id),
        client_id=str(db_entity.client_id),
        user_id=str(user_id) if user_id else None,
        new_values=update_data,
    )
    return db_entity

def delete_entity(db: Session, entity_id: int, user_id: Optional[UUID] = None) -> bool:
    """Soft delete an entity"""
    db_entity = get_entity(db, entity_id=entity_id)
    if not db_entity:
        return False

    db_entity.deleted = True
    db_entity.active = False
    db.add(db_entity)
    db.commit()
    fire_audit_log(
        action="DELETE", object_type="Entity",
        object_id=str(entity_id),
        client_id=str(db_entity.client_id),
        user_id=str(user_id) if user_id else None,
        old_values={"deleted": False}, new_values={"deleted": True},
    )
    return True

def get_entities_count_by_client(db: Session, client_id: int) -> int:
    """Get count of entities for a client"""
    return db.query(Entity).filter(
        Entity.client_id == client_id,
        Entity.deleted == False
    ).count()

def get_entities_count(db: Session) -> int:
    """Get total count of all entities"""
    return db.query(Entity).filter(Entity.deleted == False).count()

def get_entities_by_location(db: Session, country_code: str = None, state_code: str = None, city_code: str = None, skip: int = 0, limit: int = 100) -> List[Entity]:
    """Get entities by location filters"""
    query = db.query(Entity).filter(Entity.deleted == False)
    
    if country_code:
        query = query.filter(Entity.country_code == country_code)
    if state_code:
        query = query.filter(Entity.state_code == state_code)
    if city_code:
        query = query.filter(Entity.city_code == city_code)
    
    entities = query.offset(skip).limit(limit).all()
    for entity in entities:
        _decrypt_entity_fields(entity)
    return entities