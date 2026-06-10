from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from app.divisions.models.divisions import Division
from app.divisions.schemas.divisions import DivisionCreate, DivisionUpdate


def get_division(db: Session, division_id: UUID) -> Optional[Division]:
    """Get a division by ID"""
    division = db.query(Division).options(
        joinedload(Division.client),
        joinedload(Division.entity),
        joinedload(Division.department),
        joinedload(Division.parent_division)
    ).filter(
        Division.id == division_id,
        Division.is_active == True,
        Division.deleted_at.is_(None)
    ).first()
    return division


def get_division_by_code(db: Session, division_code: str, client_id: UUID) -> Optional[Division]:
    """Get a division by code within a client"""
    division = db.query(Division).filter(
        Division.division_code == division_code,
        Division.client_id == client_id,
        Division.deleted_at.is_(None)
    ).first()
    return division


def get_divisions_by_client(
    db: Session, 
    client_id: UUID, 
    entity_id: Optional[UUID] = None,
    parent_id: Optional[UUID] = None,
    skip: int = 0, 
    limit: int = 100
) -> List[Division]:
    """Get all divisions for a specific client with optional entity and parent filters"""
    query = db.query(Division).options(
        joinedload(Division.client),
        joinedload(Division.entity),
        joinedload(Division.department),
        joinedload(Division.parent_division)
    ).filter(
        Division.client_id == client_id,
        Division.is_active == True,
        Division.deleted_at.is_(None)
    )
    
    if entity_id:
        query = query.filter(Division.entity_id == entity_id)
    
    if parent_id:
        query = query.filter(Division.parent_division_id == parent_id)
    
    # Sort by newest first (FILO)
    query = query.order_by(Division.created_at.desc())
    
    divisions = query.offset(skip).limit(limit).all()
    return divisions


def get_divisions_by_entity(db: Session, entity_id: UUID, skip: int = 0, limit: int = 100) -> List[Division]:
    """Get all divisions for a specific entity"""
    divisions = db.query(Division).options(
        joinedload(Division.client),
        joinedload(Division.entity),
        joinedload(Division.department),
        joinedload(Division.parent_division)
    ).filter(
        Division.entity_id == entity_id,
        Division.is_active == True,
        Division.deleted_at.is_(None)
    ).order_by(Division.created_at.desc()).offset(skip).limit(limit).all()
    return divisions


def get_divisions_by_department(db: Session, department_id: UUID, skip: int = 0, limit: int = 100) -> List[Division]:
    """Get all divisions related to a specific department"""
    from app.departments.models.departments import Department
    
    # First, get the department to find its client_id and entity_id
    department = db.query(Department).filter(
        Department.department_id == department_id,
        Department.is_active == True,
        Department.is_deleted == False
    ).first()
    
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
    
    # Build query to find divisions related to this department
    query = db.query(Division).options(
        joinedload(Division.client),
        joinedload(Division.entity),
        joinedload(Division.department),
        joinedload(Division.parent_division)
    ).filter(
        Division.client_id == department.client_id,
        Division.is_active == True,
        Division.deleted_at.is_(None)
    )
    
    # If department has an entity_id, filter divisions by the same entity
    if department.entity_id:
        query = query.filter(Division.entity_id == department.entity_id)
    else:
        # If department has no entity, get divisions without entity for the same client
        query = query.filter(Division.entity_id.is_(None))
    
    # Sort by newest first (FILO)
    query = query.order_by(Division.created_at.desc())
    
    divisions = query.offset(skip).limit(limit).all()
    return divisions


def get_divisions_by_parent(db: Session, parent_division_id: UUID, skip: int = 0, limit: int = 100) -> List[Division]:
    """Get all child divisions for a specific parent division"""
    divisions = db.query(Division).options(
        joinedload(Division.client),
        joinedload(Division.entity),
        joinedload(Division.department),
        joinedload(Division.parent_division)
    ).filter(
        Division.parent_division_id == parent_division_id,
        Division.is_active == True,
        Division.deleted_at.is_(None)
    ).order_by(Division.created_at.desc()).offset(skip).limit(limit).all()
    return divisions


def get_all_divisions(
    db: Session, 
    client_id: Optional[UUID] = None,
    entity_id: Optional[UUID] = None,
    skip: int = 0, 
    limit: int = 100
) -> List[Division]:
    """Get all divisions with optional filtering"""
    query = db.query(Division).options(
        joinedload(Division.client),
        joinedload(Division.entity),
        joinedload(Division.department),
        joinedload(Division.parent_division)
    ).filter(
        Division.is_active == True,
        Division.deleted_at.is_(None)
    )
    
    if client_id:
        query = query.filter(Division.client_id == client_id)
    
    if entity_id:
        query = query.filter(Division.entity_id == entity_id)
    
    # Sort by newest first (FILO)
    query = query.order_by(Division.created_at.desc())
    
    divisions = query.offset(skip).limit(limit).all()
    return divisions


def get_unique_departments(db: Session) -> List[UUID]:
    """Get unique department IDs from divisions table"""
    departments = db.query(Division.department_id).filter(
        Division.is_active == True,
        Division.deleted_at.is_(None),
        Division.department_id.isnot(None)
    ).distinct().all()
    
    # Extract department IDs from tuples and filter out None values
    department_list = [dept[0] for dept in departments if dept[0]]
    return department_list


def get_unique_divisions(
    db: Session,
    department_id: Optional[UUID] = None,
    department_name: Optional[str] = None
) -> List[str]:
    """Get unique division names, optionally filtered by department_id or department name"""
    from app.departments.models.departments import Department
    
    query = db.query(Division.division_name).filter(
        Division.is_active == True,
        Division.deleted_at.is_(None),
        Division.division_name.isnot(None),
        Division.division_name != ""
    )
    
    # Filter by department_id if provided
    if department_id:
        query = query.filter(Division.department_id == department_id)
    
    # Filter by department name if provided (join with Department table)
    elif department_name:
        query = query.join(Department).filter(
            Department.department_name == department_name,
            Department.is_active == True,
            Department.is_deleted == False
        )
    
    divisions = query.distinct().all()
    
    # Extract division names from tuples and filter out None/empty values
    division_list = [div[0] for div in divisions if div[0] and div[0].strip()]
    return sorted(division_list)


def create_division(db: Session, division: DivisionCreate, user_id: Optional[UUID] = None) -> Division:
    """Create a new division"""
    # Verify client exists
    from app.clients.services.clients import get_client
    client = get_client(db, division.client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Verify entity exists if provided
    if division.entity_id:
        from app.entities.services.entity import get_entity
        entity = get_entity(db, division.entity_id)
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")
        # Verify entity belongs to the client
        if entity.client_id != division.client_id:
            raise HTTPException(status_code=400, detail="Entity does not belong to the specified client")

    # Verify department exists if provided
    if division.department_id:
        from app.departments.services.departments import get_department
        department = get_department(db, division.department_id)
        if not department:
            raise HTTPException(status_code=404, detail="Department not found")
        # Verify department belongs to the client
        if department.client_id != division.client_id:
            raise HTTPException(status_code=400, detail="Department does not belong to the specified client")

    # Check if division name already exists in the same client
    existing_division = db.query(Division).filter(
        Division.division_name == division.division_name,
        Division.client_id == division.client_id,
        Division.deleted_at.is_(None)
    ).first()
    if existing_division:
        raise HTTPException(status_code=400, detail="Division with this name already exists in the client")

    # Check if division code already exists in the same client
    existing_code = get_division_by_code(db, division.division_code, division.client_id)
    if existing_code:
        raise HTTPException(status_code=400, detail="Division code already exists for this client")

    # Verify parent division exists and belongs to same client if provided
    if division.parent_division_id:
        parent_div = get_division(db, division.parent_division_id)
        if not parent_div:
            raise HTTPException(status_code=404, detail="Parent division not found")
        if parent_div.client_id != division.client_id:
            raise HTTPException(status_code=400, detail="Parent division does not belong to the same client")

    # Create new division
    division_data = division.model_dump()
    db_division = Division(**division_data)
    
    db.add(db_division)
    db.commit()
    db.refresh(db_division)
    
    return db_division


def update_division(
    db: Session, 
    division_id: UUID, 
    division: DivisionUpdate, 
    user_id: Optional[UUID] = None
) -> Optional[Division]:
    """Update a division"""
    db_division = db.query(Division).filter(
        Division.id == division_id,
        Division.is_active == True,
        Division.deleted_at.is_(None)
    ).first()
    
    if not db_division:
        raise HTTPException(status_code=404, detail="Division not found")

    update_data = division.model_dump(exclude_unset=True)

    # Check division name uniqueness if being updated
    if "division_name" in update_data and update_data["division_name"] != db_division.division_name:
        existing_division = db.query(Division).filter(
            Division.division_name == update_data["division_name"],
            Division.client_id == db_division.client_id,
            Division.deleted_at.is_(None)
        ).first()
        if existing_division:
            raise HTTPException(status_code=400, detail="Division with this name already exists in the client")

    # Check division code uniqueness if being updated
    if "division_code" in update_data and update_data["division_code"] != db_division.division_code:
        existing_code = get_division_by_code(db, update_data["division_code"], db_division.client_id)
        if existing_code:
            raise HTTPException(status_code=400, detail="Division code already exists for this client")

    # Verify parent division if being updated
    if "parent_division_id" in update_data and update_data["parent_division_id"]:
        if update_data["parent_division_id"] == division_id:
            raise HTTPException(status_code=400, detail="Division cannot be its own parent")
        parent_div = get_division(db, update_data["parent_division_id"])
        if not parent_div:
            raise HTTPException(status_code=404, detail="Parent division not found")
        if parent_div.client_id != db_division.client_id:
            raise HTTPException(status_code=400, detail="Parent division does not belong to the same client")

    # Verify department if being updated
    if "department_id" in update_data and update_data["department_id"]:
        from app.departments.services.departments import get_department
        department = get_department(db, update_data["department_id"])
        if not department:
            raise HTTPException(status_code=404, detail="Department not found")
        if department.client_id != db_division.client_id:
            raise HTTPException(status_code=400, detail="Department does not belong to the same client")

    # Update division fields
    for key, value in update_data.items():
        setattr(db_division, key, value)
    
    db.add(db_division)
    db.commit()
    db.refresh(db_division)
    
    return db_division


def delete_division(db: Session, division_id: UUID, user_id: Optional[UUID] = None) -> bool:
    """Soft delete a division"""
    db_division = db.query(Division).filter(
        Division.id == division_id,
        Division.is_active == True,
        Division.deleted_at.is_(None)
    ).first()
    
    if not db_division:
        raise HTTPException(status_code=404, detail="Division not found")

    # Check if division has child divisions
    child_divisions = get_divisions_by_parent(db, division_id)
    if child_divisions:
        raise HTTPException(
            status_code=400, 
            detail="Cannot delete division with active child divisions"
        )

    # Perform soft delete
    db_division.is_active = False
    db_division.deleted_at = datetime.utcnow()
    
    db.add(db_division)
    db.commit()
    
    return True


def restore_division(db: Session, division_id: UUID, user_id: Optional[UUID] = None) -> Optional[Division]:
    """Restore a soft-deleted division"""
    db_division = db.query(Division).filter(
        Division.id == division_id
    ).first()
    
    if not db_division:
        raise HTTPException(status_code=404, detail="Division not found")
    
    if not db_division.deleted_at:
        raise HTTPException(status_code=400, detail="Division is not deleted")

    db_division.is_active = True
    db_division.deleted_at = None
    
    db.add(db_division)
    db.commit()
    db.refresh(db_division)
    
    return db_division


def get_divisions_count_by_client(db: Session, client_id: UUID) -> int:
    """Get count of divisions for a client"""
    return db.query(Division).filter(
        Division.client_id == client_id,
        Division.is_active == True,
        Division.deleted_at.is_(None)
    ).count()


def get_divisions_count_by_entity(db: Session, entity_id: UUID) -> int:
    """Get count of divisions for an entity"""
    return db.query(Division).filter(
        Division.entity_id == entity_id,
        Division.is_active == True,
        Division.deleted_at.is_(None)
    ).count()


def search_divisions(
    db: Session,
    client_id: UUID,
    search_term: str,
    entity_id: Optional[UUID] = None,
    skip: int = 0,
    limit: int = 100
) -> List[Division]:
    """Search divisions by name, code, or description"""
    query = db.query(Division).options(
        joinedload(Division.client),
        joinedload(Division.entity),
        joinedload(Division.department),
        joinedload(Division.parent_division)
    ).filter(
        Division.client_id == client_id,
        Division.is_active == True,
        Division.deleted_at.is_(None)
    )
    
    if entity_id:
        query = query.filter(Division.entity_id == entity_id)
    
    search_filter = f"%{search_term}%"
    query = query.filter(
        (Division.division_name.ilike(search_filter)) |
        (Division.division_code.ilike(search_filter)) |
        (Division.description.ilike(search_filter))
    )
    
    query = query.order_by(Division.created_at.desc())
    
    divisions = query.offset(skip).limit(limit).all()
    return divisions
