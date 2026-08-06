from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from app.users_groups.models.users_groups import UserGroup
from app.users_groups.schemas.users_groups import UserGroupCreate, UserGroupUpdate
from app.users_groups.exceptions import (
    UserGroupNotFoundError,
    DuplicateUserGroupNameError,
    DuplicateUserGroupCodeError,
    UserGroupTenantNotFoundError,
    UserGroupRoleNotFoundError,
    UserGroupRoleTenantMismatchError,
)
from app.infrastructure.audit_tenant import fire_audit_log


def _validate_default_role(db: Session, role_id: UUID, tenant_id: Optional[UUID]) -> None:
    """Raise 404/400 unless role_id is a user_role.id belonging to the same tenant."""
    from app.user_role.models.user_role import UserRoleBasic

    role = db.query(UserRoleBasic).filter(UserRoleBasic.user_role_id == role_id).first()
    if not role:
        raise UserGroupRoleNotFoundError(str(role_id))
    if str(role.tenant_id) != str(tenant_id):
        raise UserGroupRoleTenantMismatchError()


def get_user_group(db: Session, group_id: UUID) -> UserGroup:
    """Get a user group by ID"""
    group = db.query(UserGroup).filter(
        UserGroup.id == group_id,
        UserGroup.is_active == True,
        UserGroup.deleted_at.is_(None),
    ).first()
    if not group:
        raise UserGroupNotFoundError()
    return group


def get_user_group_by_code(db: Session, group_code: str, tenant_id: Optional[UUID]) -> Optional[UserGroup]:
    """Get a user group by code, scoped to tenant"""
    return db.query(UserGroup).filter(
        UserGroup.group_code == group_code,
        UserGroup.tenant_id == tenant_id,
        UserGroup.deleted_at.is_(None),
    ).first()


def get_all_user_groups(
    db: Session,
    tenant_id: Optional[UUID] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[UserGroup]:
    """Get all user groups with optional tenant filtering, newest first"""
    query = db.query(UserGroup).filter(
        UserGroup.is_active == True,
        UserGroup.deleted_at.is_(None),
    )

    if tenant_id:
        query = query.filter(UserGroup.tenant_id == tenant_id)

    query = query.order_by(UserGroup.created_at.desc())

    return query.offset(skip).limit(limit).all()


def create_user_group(
    db: Session,
    group: UserGroupCreate,
    tenant_id: Optional[UUID],
    user_id: Optional[UUID] = None,
    group_id: Optional[UUID] = None,
) -> UserGroup:
    """Create a new user group.

    tenant_id is not part of the request body — it is derived from the caller's
    JWT and passed in here so the column stays populated while remaining absent
    from the CRUD schema. It is None for master-DB users (token without a
    tenant_id) and a tenant UUID for tenant-DB users.

    group_id lets a caller supply the primary key instead of letting the DB
    generate one (used by onboarding, where the client generates group UUIDs so
    users can reference them in the same request). When None, the model's
    uuid4 default applies.
    """
    # Verify tenant exists (skipped for master-DB users, whose tenant_id is None)
    if tenant_id is not None:
        from app.tenants.services.tenants import get_tenant
        tenant = get_tenant(db, tenant_id)
        if not tenant:
            raise UserGroupTenantNotFoundError()

    # Verify default role exists and belongs to the same tenant, if provided
    if group.default_role_id:
        _validate_default_role(db, group.default_role_id, tenant_id)

    # Check if group name already exists for this tenant
    existing_name = db.query(UserGroup).filter(
        UserGroup.group_name == group.group_name,
        UserGroup.tenant_id == tenant_id,
        UserGroup.deleted_at.is_(None),
    ).first()
    if existing_name:
        raise DuplicateUserGroupNameError(group.group_name)

    # Check if group code already exists for this tenant
    if group.group_code:
        existing_code = get_user_group_by_code(db, group.group_code, tenant_id)
        if existing_code:
            raise DuplicateUserGroupCodeError(group.group_code)

    group_data = group.model_dump()
    db_group = UserGroup(**group_data, tenant_id=tenant_id)
    # Honor a caller-supplied primary key (onboarding); otherwise the model's
    # uuid4 default generates one.
    if group_id is not None:
        db_group.id = group_id

    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    fire_audit_log(
        action="CREATE", object_type="UserGroup",
        object_id=str(db_group.id),
        tenant_id=str(db_group.tenant_id) if db_group.tenant_id else None,
        user_id=str(user_id) if user_id else None,
        new_values={"group_name": db_group.group_name, "group_code": db_group.group_code},
    )
    return db_group


def update_user_group(
    db: Session,
    group_id: UUID,
    group: UserGroupUpdate,
    user_id: Optional[UUID] = None,
) -> UserGroup:
    """Update a user group"""
    db_group = db.query(UserGroup).filter(
        UserGroup.id == group_id,
        UserGroup.is_active == True,
        UserGroup.deleted_at.is_(None),
    ).first()

    if not db_group:
        raise UserGroupNotFoundError()

    update_data = group.model_dump(exclude_unset=True)

    # Check group name uniqueness if being updated (scoped to tenant)
    if "group_name" in update_data and update_data["group_name"] != db_group.group_name:
        existing_name = db.query(UserGroup).filter(
            UserGroup.group_name == update_data["group_name"],
            UserGroup.tenant_id == db_group.tenant_id,
            UserGroup.deleted_at.is_(None),
        ).first()
        if existing_name:
            raise DuplicateUserGroupNameError(update_data["group_name"])

    # Check group code uniqueness if being updated (scoped to tenant)
    if "group_code" in update_data and update_data["group_code"] and update_data["group_code"] != db_group.group_code:
        existing_code = get_user_group_by_code(db, update_data["group_code"], db_group.tenant_id)
        if existing_code:
            raise DuplicateUserGroupCodeError(update_data["group_code"])

    # Verify default role if being updated
    if "default_role_id" in update_data and update_data["default_role_id"]:
        _validate_default_role(db, update_data["default_role_id"], db_group.tenant_id)

    for key, value in update_data.items():
        setattr(db_group, key, value)

    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    fire_audit_log(
        action="UPDATE", object_type="UserGroup",
        object_id=str(group_id),
        tenant_id=str(db_group.tenant_id) if db_group.tenant_id else None,
        user_id=str(user_id) if user_id else None,
        new_values=update_data,
    )
    return db_group


def delete_user_group(db: Session, group_id: UUID, user_id: Optional[UUID] = None) -> bool:
    """Soft delete a user group"""
    db_group = db.query(UserGroup).filter(
        UserGroup.id == group_id,
        UserGroup.is_active == True,
        UserGroup.deleted_at.is_(None),
    ).first()

    if not db_group:
        raise UserGroupNotFoundError()

    db_group.is_active = False
    db_group.deleted_at = datetime.utcnow()

    db.add(db_group)
    db.commit()
    fire_audit_log(
        action="DELETE", object_type="UserGroup",
        object_id=str(group_id),
        tenant_id=str(db_group.tenant_id) if db_group.tenant_id else None,
        user_id=str(user_id) if user_id else None,
        old_values={"is_active": True}, new_values={"is_active": False},
    )
    return True
