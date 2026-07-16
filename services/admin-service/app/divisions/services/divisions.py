from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from app.divisions.models.divisions import Division
from app.divisions.schemas.divisions import DivisionCreate, DivisionUpdate
from app.infrastructure.audit_tenant import fire_audit_log


def get_division(db: Session, division_id: UUID) -> Optional[Division]:
    """Get a division by ID"""
    division = db.query(Division).options(
        joinedload(Division.tenant),
        joinedload(Division.entity),
        joinedload(Division.department),
        joinedload(Division.parent_division)
    ).filter(
        Division.id == division_id,
        Division.is_active == True,
        Division.deleted_at.is_(None)
    ).first()
    return division


def get_division_by_code(db: Session, division_code: str, tenant_id: UUID, entity_id: Optional[UUID] = None) -> Optional[Division]:
    """Get a division by code, scoped to entity when provided"""
    query = db.query(Division).filter(
        Division.division_code == division_code,
        Division.tenant_id == tenant_id,
        Division.deleted_at.is_(None)
    )
    if entity_id:
        query = query.filter(Division.entity_id == entity_id)
    return query.first()


def get_divisions_by_tenant(
    db: Session,
    tenant_id: UUID,
    entity_id: Optional[UUID] = None,
    parent_id: Optional[UUID] = None,
    skip: int = 0,
    limit: int = 100
) -> List[Division]:
    """Get all divisions for a specific tenant with optional entity and parent filters"""
    query = db.query(Division).options(
        joinedload(Division.tenant),
        joinedload(Division.entity),
        joinedload(Division.department),
        joinedload(Division.parent_division)
    ).filter(
        Division.tenant_id == tenant_id,
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
        joinedload(Division.tenant),
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

    # First, get the department to find its tenant_id and entity_id
    department = db.query(Department).filter(
        Department.department_id == department_id,
        Department.is_active == True,
        Department.is_deleted == False
    ).first()

    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    # Build query to find divisions related to this department
    query = db.query(Division).options(
        joinedload(Division.tenant),
        joinedload(Division.entity),
        joinedload(Division.department),
        joinedload(Division.parent_division)
    ).filter(
        Division.tenant_id == department.tenant_id,
        Division.is_active == True,
        Division.deleted_at.is_(None)
    )

    # If department has an entity_id, filter divisions by the same entity
    if department.entity_id:
        query = query.filter(Division.entity_id == department.entity_id)
    else:
        # If department has no entity, get divisions without entity for the same tenant
        query = query.filter(Division.entity_id.is_(None))

    # Sort by newest first (FILO)
    query = query.order_by(Division.created_at.desc())

    divisions = query.offset(skip).limit(limit).all()
    return divisions


def get_divisions_by_parent(db: Session, parent_division_id: UUID, skip: int = 0, limit: int = 100) -> List[Division]:
    """Get all child divisions for a specific parent division"""
    divisions = db.query(Division).options(
        joinedload(Division.tenant),
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
    tenant_id: Optional[UUID] = None,
    entity_id: Optional[UUID] = None,
    skip: int = 0,
    limit: int = 100
) -> List[Division]:
    """Get all divisions with optional filtering"""
    query = db.query(Division).options(
        joinedload(Division.tenant),
        joinedload(Division.entity),
        joinedload(Division.department),
        joinedload(Division.parent_division)
    ).filter(
        Division.is_active == True,
        Division.deleted_at.is_(None)
    )

    if tenant_id:
        query = query.filter(Division.tenant_id == tenant_id)

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
    # Verify tenant exists
    from app.tenants.services.tenants import get_tenant
    tenant = get_tenant(db, division.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Verify entity exists if provided
    if division.entity_id:
        from app.entities.services.entity import get_entity
        entity = get_entity(db, division.entity_id)
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")
        # Verify entity belongs to the tenant
        if entity.tenant_id != division.tenant_id:
            raise HTTPException(status_code=400, detail="Entity does not belong to the specified tenant")

    # Verify department exists if provided
    if division.department_id:
        from app.departments.services.departments import get_department
        department = get_department(db, division.department_id)
        if not department:
            raise HTTPException(status_code=404, detail="Department not found")
        # Verify department belongs to the tenant
        if department.tenant_id != division.tenant_id:
            raise HTTPException(status_code=400, detail="Department does not belong to the specified tenant")

    # Check if division name already exists in the same entity
    existing_division = db.query(Division).filter(
        Division.division_name == division.division_name,
        Division.entity_id == division.entity_id,
        Division.deleted_at.is_(None)
    ).first()
    if existing_division:
        raise HTTPException(status_code=400, detail="Division with this name already exists in this entity")

    # Check if division code already exists in the same entity
    existing_code = get_division_by_code(db, division.division_code, division.tenant_id, division.entity_id)
    if existing_code:
        raise HTTPException(status_code=400, detail="Division code already exists for this entity")

    # Verify parent division exists and belongs to same tenant if provided
    if division.parent_division_id:
        parent_div = get_division(db, division.parent_division_id)
        if not parent_div:
            raise HTTPException(status_code=404, detail="Parent division not found")
        if parent_div.tenant_id != division.tenant_id:
            raise HTTPException(status_code=400, detail="Parent division does not belong to the same tenant")

    # Create new division
    division_data = division.model_dump()
    db_division = Division(**division_data)

    db.add(db_division)
    db.commit()
    db.refresh(db_division)
    fire_audit_log(
        action="CREATE", object_type="Division",
        object_id=str(db_division.id),
        tenant_id=str(db_division.tenant_id),
        entity_id=str(db_division.entity_id) if db_division.entity_id else None,
        user_id=str(user_id) if user_id else None,
        new_values={"division_name": db_division.division_name, "division_code": db_division.division_code},
    )
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

    # Check division name uniqueness if being updated (scoped to entity)
    if "division_name" in update_data and update_data["division_name"] != db_division.division_name:
        existing_division = db.query(Division).filter(
            Division.division_name == update_data["division_name"],
            Division.entity_id == db_division.entity_id,
            Division.deleted_at.is_(None)
        ).first()
        if existing_division:
            raise HTTPException(status_code=400, detail="Division with this name already exists in this entity")

    # Check division code uniqueness if being updated (scoped to entity)
    if "division_code" in update_data and update_data["division_code"] != db_division.division_code:
        existing_code = get_division_by_code(db, update_data["division_code"], db_division.tenant_id, db_division.entity_id)
        if existing_code:
            raise HTTPException(status_code=400, detail="Division code already exists for this entity")

    # Verify parent division if being updated
    if "parent_division_id" in update_data and update_data["parent_division_id"]:
        if update_data["parent_division_id"] == division_id:
            raise HTTPException(status_code=400, detail="Division cannot be its own parent")
        parent_div = get_division(db, update_data["parent_division_id"])
        if not parent_div:
            raise HTTPException(status_code=404, detail="Parent division not found")
        if parent_div.tenant_id != db_division.tenant_id:
            raise HTTPException(status_code=400, detail="Parent division does not belong to the same tenant")

    # Verify department if being updated
    if "department_id" in update_data and update_data["department_id"]:
        from app.departments.services.departments import get_department
        department = get_department(db, update_data["department_id"])
        if not department:
            raise HTTPException(status_code=404, detail="Department not found")
        if department.tenant_id != db_division.tenant_id:
            raise HTTPException(status_code=400, detail="Department does not belong to the same tenant")

    # Update division fields
    for key, value in update_data.items():
        setattr(db_division, key, value)

    db.add(db_division)
    db.commit()
    db.refresh(db_division)
    fire_audit_log(
        action="UPDATE", object_type="Division",
        object_id=str(division_id),
        tenant_id=str(db_division.tenant_id),
        entity_id=str(db_division.entity_id) if db_division.entity_id else None,
        user_id=str(user_id) if user_id else None,
        new_values=update_data,
    )
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
    fire_audit_log(
        action="DELETE", object_type="Division",
        object_id=str(division_id),
        tenant_id=str(db_division.tenant_id),
        entity_id=str(db_division.entity_id) if db_division.entity_id else None,
        user_id=str(user_id) if user_id else None,
        old_values={"is_active": True}, new_values={"is_active": False},
    )
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
    fire_audit_log(
        action="RESTORE", object_type="Division",
        object_id=str(division_id),
        tenant_id=str(db_division.tenant_id),
        entity_id=str(db_division.entity_id) if db_division.entity_id else None,
        user_id=str(user_id) if user_id else None,
        old_values={"is_active": False}, new_values={"is_active": True},
    )
    return db_division


def get_divisions_count_by_tenant(db: Session, tenant_id: UUID) -> int:
    """Get count of divisions for a tenant"""
    return db.query(Division).filter(
        Division.tenant_id == tenant_id,
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
    tenant_id: UUID,
    search_term: str,
    entity_id: Optional[UUID] = None,
    skip: int = 0,
    limit: int = 100
) -> List[Division]:
    """Search divisions by name, code, or description"""
    query = db.query(Division).options(
        joinedload(Division.tenant),
        joinedload(Division.entity),
        joinedload(Division.department),
        joinedload(Division.parent_division)
    ).filter(
        Division.tenant_id == tenant_id,
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
