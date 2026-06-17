from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_, or_, desc, asc
from fastapi import HTTPException, status
from math import ceil

from app.user_role_form_permission.models.user_role_form_permission import RoleFormPermission
from app.infrastructure.audit_client import fire_audit_log
from app.user_role.models.user_role import UserRoleMain, UserRoleBasic, UserRolePermission
from app.forms.models.forms import Form
from app.user_role_form_permission.schemas.user_role_form_permission import (
    RoleFormPermissionCreate,
    RoleFormPermissionUpdate
)


class RoleFormPermissionService:
    """Service for managing role form permissions"""

    @staticmethod
    def create_role_form_permission(
        db: Session,
        permission_data: RoleFormPermissionCreate
    ) -> RoleFormPermission:
        """Create a new role form permission based on selected menus from userrole_permission"""
        try:
            # Verify userrole_permission exists and get related data
            role_permission = db.query(UserRolePermission).filter(
                UserRolePermission.id == permission_data.userrole_permission_id
            ).first()
            if not role_permission:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"User role permission with ID {permission_data.userrole_permission_id} not found"
                )

            # Get user_role_id and userrole_basic_id from the permission
            user_role_id = role_permission.user_role_id
            userrole_basic_id = role_permission.userrole_basic_id

            # Get selected menu IDs from userrole_permission
            selected_menu_ids = set()
            if role_permission.menu_permissions:
                for menu_perm in role_permission.menu_permissions:
                    if isinstance(menu_perm, dict) and 'id' in menu_perm:
                        selected_menu_ids.add(menu_perm['id'])

            # Validate that all form permissions reference selected menus
            for form_perm in permission_data.form_permissions:
                if form_perm.menu_id not in selected_menu_ids:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Menu ID {form_perm.menu_id} is not in the selected menus for this role permission"
                    )

            # Verify all forms exist
            if permission_data.form_permissions:
                form_ids = [item.id for item in permission_data.form_permissions]
                RoleFormPermissionService._verify_forms_exist(db, form_ids)

            # Convert form permissions to dict format for JSONB storage (simplified structure)
            form_perms = []
            for item in permission_data.form_permissions:
                perm_dict = {
                    "id": item.id,
                    "menu_id": item.menu_id
                }
                if item.form_access:
                    perm_dict["access"] = item.form_access
                form_perms.append(perm_dict)

            # Calculate highest form access level
            form_access_level = RoleFormPermissionService._calculate_highest_access(form_perms)

            # Create the role form permission
            db_permission = RoleFormPermission(
                user_role_id=user_role_id,
                userrole_basic_id=userrole_basic_id,
                userrole_permission_id=permission_data.userrole_permission_id,
                form_permissions=form_perms,
                form_access=form_access_level
            )

            db.add(db_permission)
            db.commit()
            db.refresh(db_permission)
            fire_audit_log(
                action="CREATE", object_type="RoleFormPermission",
                object_id=str(db_permission.id),
                new_values={"user_role_id": str(db_permission.user_role_id), "form_access": db_permission.form_access},
            )
            return db_permission

        except IntegrityError as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to create role form permission: {str(e.orig)}"
            )

    @staticmethod
    def get_role_form_permission(
        db: Session,
        permission_id: UUID
    ) -> Optional[RoleFormPermission]:
        """Get a role form permission by ID"""
        return db.query(RoleFormPermission).filter(
            RoleFormPermission.id == permission_id
        ).first()

    @staticmethod
    def get_role_form_permissions_by_user_role(
        db: Session,
        user_role_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[RoleFormPermission], int]:
        """Get all role form permissions for a specific user role with pagination"""
        query = db.query(RoleFormPermission).filter(
            RoleFormPermission.user_role_id == user_role_id
        )

        total = query.count()
        permissions = query.order_by(RoleFormPermission.sino).offset(skip).limit(limit).all()

        return permissions, total

    @staticmethod
    def get_all_role_form_permissions(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        user_role_id: Optional[UUID] = None,
        userrole_basic_id: Optional[UUID] = None,
        form_access: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> tuple[List[RoleFormPermission], int]:
        """Get all role form permissions with filtering and pagination"""
        query = db.query(RoleFormPermission)

        # Apply filters
        if user_role_id:
            query = query.filter(RoleFormPermission.user_role_id == user_role_id)

        if userrole_basic_id:
            query = query.filter(RoleFormPermission.userrole_basic_id == userrole_basic_id)

        if form_access:
            query = query.filter(RoleFormPermission.form_access == form_access)

        # Apply sorting
        if hasattr(RoleFormPermission, sort_by):
            if sort_order.lower() == "desc":
                query = query.order_by(desc(getattr(RoleFormPermission, sort_by)))
            else:
                query = query.order_by(asc(getattr(RoleFormPermission, sort_by)))

        # Get total count
        total = query.count()

        # Apply pagination
        permissions = query.offset(skip).limit(limit).all()

        return permissions, total

    @staticmethod
    def update_role_form_permission(
        db: Session,
        permission_id: UUID,
        permission_data: RoleFormPermissionUpdate
    ) -> Optional[RoleFormPermission]:
        """Update a role form permission"""
        db_permission = db.query(RoleFormPermission).filter(
            RoleFormPermission.id == permission_id
        ).first()

        if not db_permission:
            return None

        try:
            update_data = permission_data.model_dump(exclude_unset=True)

            # Update form permissions if provided
            if "form_permissions" in update_data and update_data["form_permissions"] is not None:
                # Get the role permission to validate menu selections
                role_permission = db.query(UserRolePermission).filter(
                    UserRolePermission.id == db_permission.userrole_permission_id
                ).first()

                if role_permission:
                    # Get selected menu IDs
                    selected_menu_ids = set()
                    if role_permission.menu_permissions:
                        for menu_perm in role_permission.menu_permissions:
                            if isinstance(menu_perm, dict) and 'id' in menu_perm:
                                selected_menu_ids.add(menu_perm['id'])

                    # Validate that all form permissions reference selected menus
                    for form_perm in permission_data.form_permissions:
                        if form_perm.menu_id not in selected_menu_ids:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Menu ID {form_perm.menu_id} is not in the selected menus for this role permission"
                            )

                # Verify all forms exist
                form_ids = [item.id for item in permission_data.form_permissions]
                RoleFormPermissionService._verify_forms_exist(db, form_ids)

                # Convert to dict format (simplified structure)
                form_perms = []
                for item in permission_data.form_permissions:
                    perm_dict = {
                        "id": item.id,
                        "menu_id": item.menu_id
                    }
                    if item.form_access:
                        perm_dict["access"] = item.form_access
                    form_perms.append(perm_dict)

                db_permission.form_permissions = form_perms
                db_permission.form_access = RoleFormPermissionService._calculate_highest_access(form_perms)

            db.commit()
            db.refresh(db_permission)
            fire_audit_log(
                action="UPDATE", object_type="RoleFormPermission",
                object_id=str(permission_id),
            )
            return db_permission

        except IntegrityError as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to update role form permission: {str(e.orig)}"
            )

    @staticmethod
    def delete_role_form_permission(
        db: Session,
        permission_id: UUID
    ) -> bool:
        """Delete a role form permission"""
        db_permission = db.query(RoleFormPermission).filter(
            RoleFormPermission.id == permission_id
        ).first()

        if not db_permission:
            return False

        db.delete(db_permission)
        db.commit()
        fire_audit_log(
            action="DELETE", object_type="RoleFormPermission",
            object_id=str(permission_id),
        )
        return True

    @staticmethod
    def delete_role_form_permissions_by_user_role(
        db: Session,
        user_role_id: UUID
    ) -> int:
        """Delete all role form permissions for a specific user role"""
        deleted_count = db.query(RoleFormPermission).filter(
            RoleFormPermission.user_role_id == user_role_id
        ).delete()

        db.commit()
        return deleted_count

    # ============================================================================
    # Helper Methods
    # ============================================================================

    @staticmethod
    def _verify_forms_exist(db: Session, form_ids: List[str]) -> None:
        """Verify that all forms in the array exist"""
        from uuid import UUID as UUIDType
        for form_id_str in form_ids:
            try:
                form_id = UUIDType(form_id_str)
                form = db.query(Form).filter(Form.id == form_id).first()
                if not form:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Form with ID {form_id_str} not found"
                    )
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid UUID format: {form_id_str}"
                )

    @staticmethod
    def _calculate_highest_access(permissions: List[Dict[str, Any]]) -> str:
        """
        Calculate the highest access level from a list of permissions
        Priority: write > read > disable
        """
        if not permissions:
            return "disable"

        has_write = False
        has_read = False
        has_disable = False

        for perm in permissions:
            access_list = perm.get("access", [])
            if "write" in access_list:
                has_write = True
            if "read" in access_list:
                has_read = True
            if "disable" in access_list:
                has_disable = True

        # Return highest priority access
        if has_write:
            return "write"
        elif has_read:
            return "read"
        elif has_disable:
            return "disable"
        else:
            return "disable"

    @staticmethod
    def get_statistics(
        db: Session,
        user_role_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Get statistics for role form permissions"""
        query = db.query(RoleFormPermission)

        if user_role_id:
            query = query.filter(RoleFormPermission.user_role_id == user_role_id)

        total_permissions = query.count()
        write_access = query.filter(RoleFormPermission.form_access == "write").count()
        read_access = query.filter(RoleFormPermission.form_access == "read").count()
        disabled = query.filter(RoleFormPermission.form_access == "disable").count()

        return {
            "total_permissions": total_permissions,
            "write_access": write_access,
            "read_access": read_access,
            "disabled": disabled,
            "user_role_id": str(user_role_id) if user_role_id else None
        }
