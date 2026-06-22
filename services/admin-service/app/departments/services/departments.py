from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from app.departments.models.departments import Department
from app.departments.schemas.departments import DepartmentCreate, DepartmentUpdate
from app.infrastructure.audit_client import fire_audit_log


def get_department(db: Session, department_id: UUID) -> Optional[Department]:
    """Get a department by ID"""
    department = db.query(Department).filter(
        Department.department_id == department_id,
        Department.is_deleted == False
    ).first()
    return department


def get_department_by_code(db: Session, department_code: str, client_id: UUID, entity_id: Optional[UUID] = None) -> Optional[Department]:
    """Get a department by code, scoped to entity when provided"""
    query = db.query(Department).filter(
        Department.department_code == department_code,
        Department.client_id == client_id,
        Department.is_deleted == False
    )
    if entity_id:
        query = query.filter(Department.entity_id == entity_id)
    return query.first()


def get_departments_by_client(db: Session, client_id: UUID, entity_id: Optional[UUID] = None, skip: int = 0, limit: int = 100) -> List[Department]:
    """Get all departments for a client, filtered by entity when provided"""
    query = db.query(Department).filter(
        Department.client_id == client_id,
        Department.is_deleted == False
    )
    if entity_id:
        query = query.filter(Department.entity_id == entity_id)
    return query.offset(skip).limit(limit).all()


def get_departments_by_entity(db: Session, entity_id: UUID, skip: int = 0, limit: int = 100) -> List[Department]:
    """Get all departments for a specific entity"""
    departments = db.query(Department).filter(
        Department.entity_id == entity_id,
        Department.is_deleted == False
    ).offset(skip).limit(limit).all()
    return departments


def get_departments_by_parent(db: Session, parent_department_id: UUID, skip: int = 0, limit: int = 100) -> List[Department]:
    """Get all child departments for a specific parent department"""
    departments = db.query(Department).filter(
        Department.parent_department_id == parent_department_id,
        Department.is_deleted == False
    ).offset(skip).limit(limit).all()
    return departments


def get_active_departments(db: Session, client_id: UUID, entity_id: Optional[UUID] = None, skip: int = 0, limit: int = 100) -> List[Department]:
    """Get all active departments for a client, filtered by entity when provided"""
    query = db.query(Department).filter(
        Department.client_id == client_id,
        Department.is_active == True,
        Department.is_deleted == False
    )
    if entity_id:
        query = query.filter(Department.entity_id == entity_id)
    return query.offset(skip).limit(limit).all()


def get_all_departments(db: Session, skip: int = 0, limit: int = 100) -> List[Department]:
    """Get all departments with pagination"""
    departments = db.query(Department).filter(
        Department.is_deleted == False
    ).offset(skip).limit(limit).all()
    return departments


def create_department(db: Session, department: DepartmentCreate, user_id: Optional[UUID] = None) -> Department:
    """Create a new department"""
    # Verify client exists
    from app.clients.services.clients import get_client
    client = get_client(db, department.client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Verify entity exists if provided
    if department.entity_id:
        from app.entities.services.entity import get_entity
        entity = get_entity(db, department.entity_id)
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")
        # Verify entity belongs to the client
        if entity.client_id != department.client_id:
            raise HTTPException(status_code=400, detail="Entity does not belong to the specified client")

    # Check if department code already exists within the entity
    if department.department_code:
        existing_dept = get_department_by_code(db, department.department_code, department.client_id, department.entity_id)
        if existing_dept:
            raise HTTPException(status_code=400, detail="Department code already exists for this entity")

    # Verify parent department exists and belongs to same client/entity if provided
    if department.parent_department_id:
        parent_dept = get_department(db, department.parent_department_id)
        if not parent_dept:
            raise HTTPException(status_code=404, detail="Parent department not found")
        if parent_dept.client_id != department.client_id:
            raise HTTPException(status_code=400, detail="Parent department does not belong to the same client")
        if department.entity_id and parent_dept.entity_id != department.entity_id:
            raise HTTPException(status_code=400, detail="Parent department does not belong to the same entity")

    # Manager validation removed - manager_id field doesn't exist in database

    # Create new department
    department_data = department.model_dump()
    db_department = Department(
        client_id=department_data['client_id'],
        entity_id=department_data.get('entity_id'),
        parent_department_id=department_data.get('parent_department_id'),
        department_name=department_data['department_name'],
        department_code=department_data.get('department_code'),
        description=department_data.get('description'),
        department_type=department_data.get('department_type'),
        cost_center=department_data.get('cost_center'),
        budget_info=department_data.get('budget_info', {}),
        # manager_id field removed - doesn't exist in database
        location=department_data['location'],
        phone=department_data['phone'],
        email=department_data['email'],
        annual_budget=department_data['annual_budget'],
        reporting_structure=department_data['reporting_structure'],
        department_metadata=department_data.get('department_metadata', {}),
        is_active=department_data.get('is_active', True),
        created_by=user_id,
        updated_by=user_id
    )
    
    db.add(db_department)
    db.commit()
    db.refresh(db_department)
    
    fire_audit_log(
        action="CREATE",
        object_type="Department",
        object_id=str(db_department.department_id),
        client_id=str(department.client_id),
        entity_id=str(department.entity_id) if department.entity_id else None,
        user_id=str(user_id) if user_id else None,
        new_values=department_data,
    )
    
    return db_department


def update_department(
    db: Session, 
    department_id: UUID, 
    department: DepartmentUpdate, 
    user_id: Optional[UUID] = None
) -> Optional[Department]:
    """Update a department"""
    db_department = get_department(db, department_id=department_id)
    if not db_department:
        raise HTTPException(status_code=404, detail="Department not found")

    update_data = department.model_dump(exclude_unset=True)
    old_values = {key: getattr(db_department, key) for key in update_data.keys() if hasattr(db_department, key)}

    # Check department code uniqueness if being updated (scoped to entity)
    if "department_code" in update_data and update_data["department_code"] != db_department.department_code:
        existing_dept = get_department_by_code(db, update_data["department_code"], db_department.client_id, db_department.entity_id)
        if existing_dept:
            raise HTTPException(status_code=400, detail="Department code already exists for this entity")

    # Verify parent department if being updated
    if "parent_department_id" in update_data and update_data["parent_department_id"]:
        if update_data["parent_department_id"] == department_id:
            raise HTTPException(status_code=400, detail="Department cannot be its own parent")
        parent_dept = get_department(db, update_data["parent_department_id"])
        if not parent_dept:
            raise HTTPException(status_code=404, detail="Parent department not found")
        if parent_dept.client_id != db_department.client_id:
            raise HTTPException(status_code=400, detail="Parent department does not belong to the same client")

    # Manager validation removed - manager_id field doesn't exist in database

    # Update department fields
    for key, value in update_data.items():
        setattr(db_department, key, value)

    db_department.updated_by = user_id
    
    db.add(db_department)
    db.commit()
    db.refresh(db_department)
    
    fire_audit_log(
        action="UPDATE",
        object_type="Department",
        object_id=str(department_id),
        client_id=str(db_department.client_id),
        entity_id=str(db_department.entity_id) if db_department.entity_id else None,
        user_id=str(user_id) if user_id else None,
        old_values=old_values,
        new_values=update_data,
    )
    
    return db_department


def delete_department(db: Session, department_id: UUID, user_id: Optional[UUID] = None) -> bool:
    """Soft delete a department"""
    db_department = get_department(db, department_id=department_id)
    if not db_department:
        raise HTTPException(status_code=404, detail="Department not found")

    # Check if department has child departments
    child_departments = get_departments_by_parent(db, department_id)
    if child_departments:
        raise HTTPException(
            status_code=400, 
            detail="Cannot delete department with active child departments"
        )
    
    # Check if department has associated active users (optional check)
    # TODO: Implement when User and UserDepartment models are available
    # try:
    #     from app.user_setup.models.user_setup import User
    #     from app.models.associations import UserDepartment
    #     users_count = db.query(UserDepartment).join(User).filter(
    #         UserDepartment.department_id == department_id,
    #         User.is_active == 1
    #     ).count()
    #     if users_count > 0:
    #         raise HTTPException(
    #             status_code=400, 
    #             detail="Cannot delete department with associated active users"
    #         )
    # except ImportError:
    #     # Skip user check if associations model doesn't exist
    #     pass
    pass  # Skip user validation for now

    old_values = {
        "department_name": db_department.department_name,
        "is_deleted": db_department.is_deleted,
        "is_active": db_department.is_active
    }

    db_department.is_deleted = True
    db_department.is_active = False
    db_department.deleted_at = datetime.utcnow()
    db_department.updated_by = user_id
    
    db.add(db_department)
    db.commit()
    
    fire_audit_log(
        action="DELETE",
        object_type="Department",
        object_id=str(department_id),
        client_id=str(db_department.client_id),
        entity_id=str(db_department.entity_id) if db_department.entity_id else None,
        user_id=str(user_id) if user_id else None,
        old_values=old_values,
        new_values={"is_deleted": True, "is_active": False},
    )
    
    return True


def restore_department(db: Session, department_id: UUID, user_id: Optional[UUID] = None) -> Optional[Department]:
    """Restore a soft-deleted department"""
    db_department = db.query(Department).filter(
        Department.department_id == department_id
    ).first()
    
    if not db_department:
        raise HTTPException(status_code=404, detail="Department not found")
    
    if not db_department.is_deleted:
        raise HTTPException(status_code=400, detail="Department is not deleted")

    db_department.is_deleted = False
    db_department.is_active = True
    db_department.deleted_at = None
    db_department.updated_by = user_id
    
    db.add(db_department)
    db.commit()
    db.refresh(db_department)
    
    fire_audit_log(
        action="RESTORE",
        object_type="Department",
        object_id=str(department_id),
        client_id=str(db_department.client_id),
        entity_id=str(db_department.entity_id) if db_department.entity_id else None,
        user_id=str(user_id) if user_id else None,
        old_values={"is_deleted": True},
        new_values={"is_deleted": False, "is_active": True},
    )
    
    return db_department


def get_department_hierarchy(db: Session, department_id: UUID) -> dict:
    """Get the complete hierarchy for a department (parents and children)"""
    department = get_department(db, department_id)
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
    
    # Get parent hierarchy
    parents = []
    current = department
    while current.parent_department_id:
        parent = get_department(db, current.parent_department_id)
        if parent:
            parents.insert(0, {
                "department_id": str(parent.department_id),
                "department_name": parent.department_name,
                "department_code": parent.department_code
            })
            current = parent
        else:
            break
    
    # Get children recursively
    def get_children_recursive(dept_id: UUID):
        children = get_departments_by_parent(db, dept_id)
        result = []
        for child in children:
            child_data = {
                "department_id": str(child.department_id),
                "department_name": child.department_name,
                "department_code": child.department_code,
                "children": get_children_recursive(child.department_id)
            }
            result.append(child_data)
        return result
    
    children = get_children_recursive(department_id)
    
    return {
        "department": {
            "department_id": str(department.department_id),
            "department_name": department.department_name,
            "department_code": department.department_code
        },
        "parents": parents,
        "children": children
    }


def get_departments_count_by_client(db: Session, client_id: UUID) -> int:
    """Get count of departments for a client"""
    return db.query(Department).filter(
        Department.client_id == client_id,
        Department.is_deleted == False
    ).count()


def get_departments_count_by_entity(db: Session, entity_id: UUID) -> int:
    """Get count of departments for an entity"""
    return db.query(Department).filter(
        Department.entity_id == entity_id,
        Department.is_deleted == False
    ).count()


def search_departments(
    db: Session,
    client_id: UUID,
    search_term: str,
    entity_id: Optional[UUID] = None,
    skip: int = 0,
    limit: int = 100
) -> List[Department]:
    """Search departments by name, code, or description"""
    query = db.query(Department).filter(
        Department.client_id == client_id,
        Department.is_deleted == False
    )
    
    if entity_id:
        query = query.filter(Department.entity_id == entity_id)
    
    search_filter = f"%{search_term}%"
    query = query.filter(
        (Department.department_name.ilike(search_filter)) |
        (Department.department_code.ilike(search_filter)) |
        (Department.description.ilike(search_filter))
    )
    
    departments = query.offset(skip).limit(limit).all()
    return departments

