from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.departments.exceptions import (
    DepartmentNotFoundError,
    DuplicateDepartmentCodeError,
    DepartmentTenantNotFoundError,
    DepartmentEntityNotFoundError,
    DepartmentNotDeletedError,
)
from datetime import datetime

from app.departments.models.departments import Department
from app.departments.schemas.departments import DepartmentCreate, DepartmentUpdate
from app.infrastructure.audit_tenant import fire_audit_log


def get_department(db: Session, department_id: UUID) -> Optional[Department]:
    """Get a department by ID"""
    department = db.query(Department).filter(
        Department.department_id == department_id,
        Department.is_deleted == False
    ).first()
    return department


def get_department_by_code(db: Session, department_code: str, tenant_id: UUID, entity_id: Optional[UUID] = None) -> Optional[Department]:
    """Get a department by code, scoped to entity when provided"""
    query = db.query(Department).filter(
        Department.department_code == department_code,
        Department.tenant_id == tenant_id,
        Department.is_deleted == False
    )
    if entity_id:
        query = query.filter(Department.entity_id == entity_id)
    return query.first()


def get_departments_by_tenant(db: Session, tenant_id: UUID, entity_id: Optional[UUID] = None, skip: int = 0, limit: int = 100) -> List[Department]:
    """Get all departments for a tenant, filtered by entity when provided"""
    query = db.query(Department).filter(
        Department.tenant_id == tenant_id,
        Department.is_deleted == False
    )
    if entity_id:
        query = query.filter(Department.entity_id == entity_id)
    return query.offset(skip).limit(limit).all()


def get_departments_by_entity(
    db: Session, entity_id: UUID, skip: int = 0, limit: int = 100,
    scoped_ids: Optional[List[UUID]] = None,
) -> List[Department]:
    """Get all departments for a specific entity"""
    query = db.query(Department).filter(
        Department.entity_id == entity_id,
        Department.is_deleted == False
    )
    if scoped_ids is not None:
        query = query.filter(Department.department_id.in_(scoped_ids))
    return query.offset(skip).limit(limit).all()


def get_active_departments(db: Session, tenant_id: UUID, entity_id: Optional[UUID] = None, skip: int = 0, limit: int = 100) -> List[Department]:
    """Get all active departments for a tenant, filtered by entity when provided"""
    query = db.query(Department).filter(
        Department.tenant_id == tenant_id,
        Department.is_active == True,
        Department.is_deleted == False
    )
    if entity_id:
        query = query.filter(Department.entity_id == entity_id)
    return query.offset(skip).limit(limit).all()


def get_all_departments(
    db: Session, skip: int = 0, limit: int = 100,
    scoped_ids: Optional[List[UUID]] = None,
) -> List[Department]:
    """Get all departments with pagination"""
    query = db.query(Department).filter(Department.is_deleted == False)
    if scoped_ids is not None:
        query = query.filter(Department.department_id.in_(scoped_ids))
    return query.offset(skip).limit(limit).all()


def create_department(
    db: Session,
    department: DepartmentCreate,
    tenant_id: Optional[UUID],
    user_id: Optional[UUID] = None,
    department_id: Optional[UUID] = None,
) -> Department:
    """Create a new department.

    tenant_id is not part of the request body — it is derived from the caller's
    JWT and passed in here so the column stays populated while remaining absent
    from the CRUD schema. It is None for master-DB users (token without a
    tenant_id) and a tenant UUID for tenant-DB users.

    department_id lets a caller supply the primary key instead of letting the DB
    generate one (used by onboarding, where the client generates department UUIDs
    so divisions/job_codes can reference them in the same request). When None, the
    model's uuid4 default applies.
    """
    # Verify tenant exists (skipped for master-DB users, whose tenant_id is None)
    if tenant_id is not None:
        from app.tenants.services.tenants import get_tenant
        tenant = get_tenant(db, tenant_id)
        if not tenant:
            raise DepartmentTenantNotFoundError(str(tenant_id))

    # Verify entity exists if provided
    if department.entity_id:
        from app.entities.services.entity import get_entity
        entity = get_entity(db, department.entity_id)
        if not entity:
            raise DepartmentEntityNotFoundError(str(department.entity_id))
        # Entities live in this tenant's own DB, so an existing entity is
        # inherently tenant-scoped — no separate tenant-match check needed.

    # Check if department code already exists within the entity
    if department.department_code:
        existing_dept = get_department_by_code(db, department.department_code, tenant_id, department.entity_id)
        if existing_dept:
            raise DuplicateDepartmentCodeError()

    # Create new department
    department_data = department.model_dump()
    db_department = Department(
        tenant_id=tenant_id,
        entity_id=department_data.get('entity_id'),
        department_name=department_data['department_name'],
        department_code=department_data.get('department_code'),
        department_type=department_data.get('department_type'),
        cost_center=department_data.get('cost_center'),
        department_head=department_data.get('department_head'),
        location=department_data['location'],
        phone=department_data['phone'],
        email=department_data['email'],
        annual_budget=department_data['annual_budget'],
        reporting_structure=department_data.get('reporting_structure'),
        is_active=department_data.get('is_active', True),
        created_by=user_id,
        updated_by=user_id
    )
    # Honor a caller-supplied primary key (onboarding); otherwise the model's
    # uuid4 default generates one.
    if department_id is not None:
        db_department.department_id = department_id

    db.add(db_department)
    db.commit()
    db.refresh(db_department)

    fire_audit_log(
        action="CREATE",
        object_type="Department",
        object_id=str(db_department.department_id),
        tenant_id=str(tenant_id) if tenant_id else None,
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
        raise DepartmentNotFoundError()

    update_data = department.model_dump(exclude_unset=True)
    old_values = {key: getattr(db_department, key) for key in update_data.keys() if hasattr(db_department, key)}

    # Check department code uniqueness if being updated (scoped to entity)
    if "department_code" in update_data and update_data["department_code"] != db_department.department_code:
        existing_dept = get_department_by_code(db, update_data["department_code"], db_department.tenant_id, db_department.entity_id)
        if existing_dept:
            raise DuplicateDepartmentCodeError()

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
        tenant_id=str(db_department.tenant_id),
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
        raise DepartmentNotFoundError()

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
        tenant_id=str(db_department.tenant_id),
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
        raise DepartmentNotFoundError()

    if not db_department.is_deleted:
        raise DepartmentNotDeletedError()

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
        tenant_id=str(db_department.tenant_id),
        entity_id=str(db_department.entity_id) if db_department.entity_id else None,
        user_id=str(user_id) if user_id else None,
        old_values={"is_deleted": True},
        new_values={"is_deleted": False, "is_active": True},
    )

    return db_department


def get_departments_count_by_tenant(db: Session, tenant_id: UUID) -> int:
    """Get count of departments for a tenant"""
    return db.query(Department).filter(
        Department.tenant_id == tenant_id,
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
    tenant_id: UUID,
    search_term: str,
    entity_id: Optional[UUID] = None,
    skip: int = 0,
    limit: int = 100
) -> List[Department]:
    """Search departments by name or code"""
    query = db.query(Department).filter(
        Department.tenant_id == tenant_id,
        Department.is_deleted == False
    )

    if entity_id:
        query = query.filter(Department.entity_id == entity_id)

    search_filter = f"%{search_term}%"
    query = query.filter(
        (Department.department_name.ilike(search_filter)) |
        (Department.department_code.ilike(search_filter))
    )

    departments = query.offset(skip).limit(limit).all()
    return departments
