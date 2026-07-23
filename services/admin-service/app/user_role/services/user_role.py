from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.user_role.models.user_role import UserRoleMain, UserRoleBasic, UserRolePermission, UserRoleConditional
from app.infrastructure.audit_tenant import fire_audit_log
from app.menus.models.menu import Menu
from app.forms.models.forms import Form
from app.user_role.schemas.user_role import (
    UserRoleBasicCreate,
    UserRoleBasicUpdate,
    UserRolePermissionCreate,
    UserRolePermissionUpdate,
    UserRoleConditionalCreate,
    UserRoleConditionalUpdate,
    UserRoleCreateWithDetails,
    EntityReference,
    AvailableEntitiesResponse
)


class UserRoleService:
    """Service for managing user roles and their permissions/conditionals"""

    # ============================================================================
    # UserRoleBasic CRUD Operations
    # ============================================================================

    @staticmethod
    def create_user_role(db: Session, role_data: UserRoleBasicCreate) -> UserRoleBasic:
        """Create a new user role with parent UserRoleMain record"""
        try:
            # Create parent UserRoleMain record first
            db_user_role_main = UserRoleMain()
            db.add(db_user_role_main)
            db.flush()  # Get the ID without committing

            # Create UserRoleBasic record with reference to parent
            db_role = UserRoleBasic(
                user_role_id=db_user_role_main.id,
                **role_data.model_dump()
            )
            db.add(db_role)
            db.commit()
            db.refresh(db_role)
            fire_audit_log(
                action="CREATE", object_type="UserRole",
                object_id=str(db_role.id),
                new_values={"role_name": db_role.role_name, "role_code": db_role.role_code},
            )
            return db_role
        except IntegrityError as e:
            db.rollback()
            if "role_name" in str(e.orig):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Role name '{role_data.role_name}' already exists for this client"
                )
            elif "role_code" in str(e.orig):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Role code '{role_data.role_code}' already exists for this client"
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create user role"
            )

    @staticmethod
    def get_user_role(db: Session, role_id: UUID) -> Optional[UserRoleBasic]:
        """Get a user role by ID"""
        return db.query(UserRoleBasic).filter(UserRoleBasic.id == role_id).first()

    @staticmethod
    def get_user_role_with_details(db: Session, role_id: UUID) -> Optional[UserRoleBasic]:
        """Get a user role with all permissions and conditionals (role_id is UserRoleMain.id)"""
        # Load the UserRoleMain with all relationships
        db_user_role_main = (
            db.query(UserRoleMain)
            .options(
                joinedload(UserRoleMain.basic),
                joinedload(UserRoleMain.permissions),
                joinedload(UserRoleMain.conditionals)
            )
            .filter(UserRoleMain.id == role_id)
            .first()
        )

        if not db_user_role_main or not db_user_role_main.basic:
            return None

        # Return the basic info with loaded relationships
        return db_user_role_main.basic

    @staticmethod
    def get_all_user_roles(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = False,
        tenant_id: Optional[UUID] = None
    ) -> List[UserRoleBasic]:
        """Get all user roles, filtered by tenant when provided"""
        query = db.query(UserRoleBasic)

        if tenant_id:
            query = query.filter(UserRoleBasic.tenant_id == tenant_id)

        if active_only:
            query = query.filter(UserRoleBasic.active == True)

        return query.offset(skip).limit(limit).all()

    @staticmethod
    def update_user_role(
        db: Session,
        role_id: UUID,
        role_data: UserRoleBasicUpdate
    ) -> Optional[UserRoleBasic]:
        """Update a user role"""
        db_role = db.query(UserRoleBasic).filter(UserRoleBasic.id == role_id).first()
        
        if not db_role:
            return None

        try:
            update_data = role_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_role, field, value)
            
            db.commit()
            db.refresh(db_role)
            fire_audit_log(
                action="UPDATE", object_type="UserRole",
                object_id=str(role_id),
                new_values=update_data,
            )
            return db_role
        except IntegrityError as e:
            db.rollback()
            if "role_name" in str(e.orig):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Role name already exists"
                )
            elif "role_code" in str(e.orig):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Role code already exists"
                )
            raise

    @staticmethod
    def delete_user_role(db: Session, role_id: UUID) -> bool:
        """Delete a user role (cascades to permissions and conditionals) - role_id is UserRoleMain.id"""
        db_role_main = db.query(UserRoleMain).filter(UserRoleMain.id == role_id).first()
        
        if not db_role_main:
            return False
        
        db.delete(db_role_main)
        db.commit()
        fire_audit_log(
            action="DELETE", object_type="UserRole",
            object_id=str(role_id),
        )
        return True

    # ============================================================================
    # UserRolePermission CRUD Operations
    # ============================================================================

    @staticmethod
    def create_permission(db: Session, permission_data: UserRolePermissionCreate) -> UserRolePermission:
        """Create a new permission for a user role with individual access per menu/form"""
        # Verify the userrole_basic exists and get user_role_id from it
        basic_role = db.query(UserRoleBasic).filter(UserRoleBasic.id == permission_data.userrole_basic_id).first()
        if not basic_role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User role basic with ID {permission_data.userrole_basic_id} not found"
            )
        
        # Get user_role_id from userrole_basic (automatic fetch)
        user_role_id = basic_role.user_role_id

        # Verify menu permissions - each item now has a single ID
        if permission_data.menu_permissions:
            menu_ids = [item.id for item in permission_data.menu_permissions]
            UserRoleService._verify_menus_exist(db, menu_ids)

        # Form permissions removed - not needed

        # Convert Pydantic models to dict for JSONB storage
        # Store with individual access fields (menu_access)
        menu_perms = []
        for item in (permission_data.menu_permissions or []):
            perm_dict = {"id": item.id}
            if item.application_id:
                perm_dict["application_id"] = item.application_id
            if item.modules_id:
                perm_dict["modules_id"] = item.modules_id
            if item.menu_access:
                perm_dict["access"] = item.menu_access
            menu_perms.append(perm_dict)
        
        # Form permissions removed - not needed
        
        # Calculate the highest access level for menus
        menu_access_level = UserRoleService._calculate_highest_access(menu_perms)
        
        db_permission = UserRolePermission(
            user_role_id=user_role_id,  # Use the auto-fetched user_role_id
            userrole_basic_id=permission_data.userrole_basic_id,
            menu_permissions=menu_perms,
            # form_permissions removed
            menu_access=menu_access_level,
            # form_access removed
        )
        db.add(db_permission)
        db.commit()
        db.refresh(db_permission)
        return db_permission

    @staticmethod
    def get_permissions_by_role(db: Session, role_id: UUID) -> List[UserRolePermission]:
        """Get all permissions for a specific user role"""
        return db.query(UserRolePermission).filter(UserRolePermission.user_role_id == role_id).all()

    @staticmethod
    def update_permission(
        db: Session,
        permission_id: UUID,
        permission_data: UserRolePermissionUpdate
    ) -> Optional[UserRolePermission]:
        """Update a permission with individual access per menu/form"""
        db_permission = db.query(UserRolePermission).filter(UserRolePermission.id == permission_id).first()

        if not db_permission:
            return None

        update_data = permission_data.model_dump(exclude_unset=True)

        # Verify userrole_basic if being updated
        if "userrole_basic_id" in update_data and update_data["userrole_basic_id"]:
            basic_role = db.query(UserRoleBasic).filter(UserRoleBasic.id == update_data["userrole_basic_id"]).first()
            if not basic_role:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"User role basic with ID {update_data['userrole_basic_id']} not found"
                )

        # Verify menu permissions if being updated - each item has a single ID
        if "menu_permissions" in update_data and update_data["menu_permissions"]:
            menu_ids = [item.id for item in permission_data.menu_permissions]
            UserRoleService._verify_menus_exist(db, menu_ids)
            # Convert to dict with individual access fields
            menu_perms = []
            for item in permission_data.menu_permissions:
                perm_dict = {"id": item.id}
                if item.application_id:
                    perm_dict["application_id"] = item.application_id
                if item.modules_id:
                    perm_dict["modules_id"] = item.modules_id
                if item.menu_access:
                    perm_dict["access"] = item.menu_access
                menu_perms.append(perm_dict)
            update_data["menu_permissions"] = menu_perms

        # Form permissions removed - not needed

        for field, value in update_data.items():
            setattr(db_permission, field, value)

        db.commit()
        db.refresh(db_permission)
        return db_permission

    @staticmethod
    def delete_permission(db: Session, permission_id: UUID) -> bool:
        """Delete a permission"""
        db_permission = db.query(UserRolePermission).filter(UserRolePermission.id == permission_id).first()
        
        if not db_permission:
            return False
        
        db.delete(db_permission)
        db.commit()
        return True

    # ============================================================================
    # UserRoleConditional CRUD Operations
    # ============================================================================

    @staticmethod
    def create_conditional(db: Session, conditional_data: UserRoleConditionalCreate) -> UserRoleConditional:
        """Create a new conditional for a user role"""
        # Verify the user role exists (check UserRoleMain parent table)
        role = db.query(UserRoleMain).filter(UserRoleMain.id == conditional_data.user_role_id).first()
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User role with ID {conditional_data.user_role_id} not found"
            )

        # Verify the userrole_permission exists
        permission = db.query(UserRolePermission).filter(UserRolePermission.id == conditional_data.userrole_permission_id).first()
        if not permission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User role permission with ID {conditional_data.userrole_permission_id} not found"
            )

        db_conditional = UserRoleConditional(**conditional_data.model_dump())
        db.add(db_conditional)
        db.commit()
        db.refresh(db_conditional)
        return db_conditional

    @staticmethod
    def get_conditionals_by_role(db: Session, role_id: UUID) -> List[UserRoleConditional]:
        """Get all conditionals for a specific user role"""
        return db.query(UserRoleConditional).filter(UserRoleConditional.user_role_id == role_id).all()

    @staticmethod
    def update_conditional(
        db: Session,
        conditional_id: UUID,
        conditional_data: UserRoleConditionalUpdate
    ) -> Optional[UserRoleConditional]:
        """Update a conditional"""
        db_conditional = db.query(UserRoleConditional).filter(UserRoleConditional.id == conditional_id).first()

        if not db_conditional:
            return None

        update_data = conditional_data.model_dump(exclude_unset=True)

        # Verify userrole_permission if being updated
        if "userrole_permission_id" in update_data and update_data["userrole_permission_id"]:
            permission = db.query(UserRolePermission).filter(UserRolePermission.id == update_data["userrole_permission_id"]).first()
            if not permission:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"User role permission with ID {update_data['userrole_permission_id']} not found"
                )

        for field, value in update_data.items():
            setattr(db_conditional, field, value)

        db.commit()
        db.refresh(db_conditional)
        return db_conditional

    @staticmethod
    def delete_conditional(db: Session, conditional_id: UUID) -> bool:
        """Delete a conditional"""
        db_conditional = db.query(UserRoleConditional).filter(UserRoleConditional.id == conditional_id).first()
        
        if not db_conditional:
            return False
        
        db.delete(db_conditional)
        db.commit()
        return True

    # ============================================================================
    # Combined Operations
    # ============================================================================

    @staticmethod
    def create_user_role_with_details(db: Session, role_data: UserRoleCreateWithDetails) -> UserRoleBasic:
        """Create a user role with permissions and conditionals in one transaction"""
        try:
            # Create parent UserRoleMain record first
            db_user_role_main = UserRoleMain()
            db.add(db_user_role_main)
            db.flush()  # Get the ID without committing

            # Create the basic role with reference to parent
            db_role = UserRoleBasic(
                user_role_id=db_user_role_main.id,
                **role_data.basic.model_dump()
            )
            db.add(db_role)
            db.flush()

            # Create permissions (at least one permission is required if conditionals exist)
            created_permission_id = None
            if role_data.permissions:
                for perm_data in role_data.permissions:
                    # Verify menu permissions - each item has a single ID
                    if perm_data.menu_permissions:
                        menu_ids = [item.id for item in perm_data.menu_permissions]
                        UserRoleService._verify_menus_exist(db, menu_ids)

                    # Form permissions removed - not needed

                    # Convert Pydantic models to dict for JSONB storage
                    menu_perms = []
                    for item in (perm_data.menu_permissions or []):
                        perm_dict = {"id": item.id}
                        if item.application_id:
                            perm_dict["application_id"] = item.application_id
                        if item.modules_id:
                            perm_dict["modules_id"] = item.modules_id
                        if item.menu_access:
                            perm_dict["access"] = item.menu_access
                        menu_perms.append(perm_dict)
                    
                    # Form permissions removed - not needed
                    
                    # Calculate the highest access level for menus
                    menu_access_level = UserRoleService._calculate_highest_access(menu_perms)

                    db_permission = UserRolePermission(
                        user_role_id=db_user_role_main.id,
                        userrole_basic_id=db_role.id,
                        menu_permissions=menu_perms,
                        # form_permissions removed
                        menu_access=menu_access_level,
                        # form_access removed
                    )
                    db.add(db_permission)
                    db.flush()  # Get the permission ID
                    created_permission_id = db_permission.id
            elif role_data.conditionals:
                # If conditionals exist but no permissions provided, create an empty permission entry
                db_permission = UserRolePermission(
                    user_role_id=db_user_role_main.id,
                    userrole_basic_id=db_role.id,
                    menu_permissions=[],
                    # form_permissions removed
                    menu_access='disable',
                    # form_access removed
                )
                db.add(db_permission)
                db.flush()  # Get the permission ID
                created_permission_id = db_permission.id

            # Create conditionals (requires a permission to exist)
            if role_data.conditionals and created_permission_id:
                for cond_data in role_data.conditionals:
                    db_conditional = UserRoleConditional(
                        user_role_id=db_user_role_main.id,
                        userrole_permission_id=created_permission_id,
                        userrole_basic_id=db_role.id,
                        **cond_data.model_dump()
                    )
                    db.add(db_conditional)

            db.commit()
            db.refresh(db_role)

            # Load relationships
            return UserRoleService.get_user_role_with_details(db, db_user_role_main.id)

        except IntegrityError as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to create user role: {str(e.orig)}"
            )

    @staticmethod
    def update_user_role_with_details(
        db: Session,
        role_id: UUID,
        role_data: "UserRoleUpdateWithDetails"
    ) -> Optional[UserRoleBasic]:
        """Update a user role with permissions and conditionals in one transaction - role_id is UserRoleMain.id"""
        try:
            # Get the existing UserRoleMain
            db_user_role_main = db.query(UserRoleMain).filter(UserRoleMain.id == role_id).first()
            if not db_user_role_main:
                return None

            # Get the UserRoleBasic
            db_role = db.query(UserRoleBasic).filter(UserRoleBasic.user_role_id == role_id).first()
            if not db_role:
                return None

            # Update basic role information if provided
            if role_data.basic:
                update_data = role_data.basic.model_dump(exclude_unset=True)
                for field, value in update_data.items():
                    setattr(db_role, field, value)

            # Update permissions if provided (replace all)
            if role_data.permissions is not None:
                # Delete existing permissions
                db.query(UserRolePermission).filter(
                    UserRolePermission.user_role_id == role_id
                ).delete()

                # Create new permissions
                for perm_data in role_data.permissions:
                    # Build JSONB structures
                    menu_perms = []
                    for item in (perm_data.menu_permissions or []):
                        perm_dict = {"id": item.id}
                        if hasattr(item, 'application_id') and item.application_id:
                            perm_dict["application_id"] = item.application_id
                        if hasattr(item, 'modules_id') and item.modules_id:
                            perm_dict["modules_id"] = item.modules_id
                        if hasattr(item, 'menu_access') and item.menu_access:
                            perm_dict["access"] = item.menu_access
                        menu_perms.append(perm_dict)
                    
                    # Form permissions removed - not needed

                    db_permission = UserRolePermission(
                        user_role_id=db_role.user_role_id,
                        userrole_basic_id=db_role.id,
                        menu_permissions=menu_perms,
                        # form_permissions removed
                        menu_access=menu_perms,
                        # form_access removed
                    )
                    db.add(db_permission)

            # Update conditionals if provided (replace all)
            if role_data.conditionals is not None:
                # Delete existing conditionals
                db.query(UserRoleConditional).filter(
                    UserRoleConditional.user_role_id == role_id
                ).delete()

                # Create new conditionals
                for cond_data in role_data.conditionals:
                    # Get a permission ID if exists (required for conditional)
                    permission = db.query(UserRolePermission).filter(
                        UserRolePermission.user_role_id == role_id
                    ).first()
                    
                    if permission:
                        db_conditional = UserRoleConditional(
                            user_role_id=role_id,
                            userrole_permission_id=permission.id,
                            userrole_basic_id=db_role.id,
                            **cond_data.model_dump()
                        )
                        db.add(db_conditional)

            db.commit()
            db.refresh(db_role)

            # Return with all details
            return UserRoleService.get_user_role_with_details(db, role_id)

        except IntegrityError as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to update user role: {str(e.orig)}"
            )
        except Exception as e:
            db.rollback()
            raise

    # ============================================================================
    # Helper Methods
    # ============================================================================

    @staticmethod
    def _verify_menu_exists(db: Session, menu_id: UUID) -> None:
        """Verify that a menu exists (legacy - single ID)"""
        menu = db.query(Menu).filter(Menu.id == menu_id).first()
        if not menu:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Menu with ID {menu_id} not found"
            )

    @staticmethod
    def _verify_menus_exist(db: Session, menu_ids: List[str]) -> None:
        """Verify that all menus in the array exist"""
        from uuid import UUID as UUIDType
        for menu_id_str in menu_ids:
            try:
                menu_id = UUIDType(menu_id_str)
                menu = db.query(Menu).filter(Menu.id == menu_id).first()
                if not menu:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Menu with ID {menu_id_str} not found"
                    )
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid UUID format: {menu_id_str}"
                )

    @staticmethod
    def _verify_form_exists(db: Session, form_id: UUID) -> None:
        """Verify that a form exists (legacy - single ID)"""
        form = db.query(Form).filter(Form.id == form_id).first()
        if not form:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Form with ID {form_id} not found"
            )

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
    def get_available_entities(db: Session) -> AvailableEntitiesResponse:
        """Get all available entities (menus, forms) that can be assigned to roles"""
        # Fetch menus
        menus = db.query(Menu).filter(Menu.is_active == True).all()
        menu_refs = [
            EntityReference(
                entity_type="menu",
                entity_id=menu.id,
                name=menu.name,
                access=menu.access or ["read"]
            )
            for menu in menus
        ]

        # Fetch forms
        forms = db.query(Form).all()
        form_refs = [
            EntityReference(
                entity_type="form",
                entity_id=form.id,
                name=form.name,
                access=form.get_effective_access()
            )
            for form in forms
        ]

        return AvailableEntitiesResponse(
            menus=menu_refs,
            forms=form_refs
        )

    # ============================================================================
    # Additional Helper Methods for User Form Permissions
    # ============================================================================

    @staticmethod
    def get_user_role_basic(db: Session, role_id: UUID) -> Optional[UserRoleBasic]:
        """Get a user role basic by ID (alias for get_user_role)"""
        return UserRoleService.get_user_role(db, role_id)

    @staticmethod
    def get_or_create_user_role(db: Session, basic_role_id: UUID) -> UserRoleMain:
        """Get or create UserRoleMain for a given UserRoleBasic ID"""
        # Get the basic role
        basic_role = db.query(UserRoleBasic).filter(UserRoleBasic.id == basic_role_id).first()
        if not basic_role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User role basic with ID {basic_role_id} not found"
            )
        
        # Get the UserRoleMain
        user_role_main = db.query(UserRoleMain).filter(UserRoleMain.id == basic_role.user_role_id).first()
        if not user_role_main:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User role main with ID {basic_role.user_role_id} not found"
            )
        
        return user_role_main

    @staticmethod
    def get_user_role_permissions_by_basic_id(db: Session, basic_role_id: UUID) -> List[UserRolePermission]:
        """Get all permissions for a user role by basic role ID"""
        # Get the basic role to find user_role_id
        basic_role = db.query(UserRoleBasic).filter(UserRoleBasic.id == basic_role_id).first()
        if not basic_role:
            return []
        
        # Get permissions using user_role_id
        return db.query(UserRolePermission).filter(
            UserRolePermission.user_role_id == basic_role.user_role_id
        ).all()

    @staticmethod
    def create_user_role_permission(db: Session, permission_data: Dict[str, Any]) -> UserRolePermission:
        """Create a new user role permission from dict data"""
        # Form permissions removed - not needed
        
        # Convert menu_permissions if present
        menu_perms = []
        if "menu_permissions" in permission_data and permission_data["menu_permissions"]:
            for item in permission_data["menu_permissions"]:
                if isinstance(item, dict):
                    perm_dict = {"id": item.get("id")}
                    if item.get("application_id"):
                        perm_dict["application_id"] = item["application_id"]
                    if item.get("modules_id"):
                        perm_dict["modules_id"] = item["modules_id"]
                    if item.get("menu_access"):
                        perm_dict["access"] = item["menu_access"]
                    menu_perms.append(perm_dict)
                else:
                    # Handle Pydantic model
                    perm_dict = {"id": item.id}
                    if hasattr(item, 'application_id') and item.application_id:
                        perm_dict["application_id"] = item.application_id
                    if hasattr(item, 'modules_id') and item.modules_id:
                        perm_dict["modules_id"] = item.modules_id
                    if hasattr(item, 'menu_access') and item.menu_access:
                        perm_dict["access"] = item.menu_access
                    menu_perms.append(perm_dict)
        
        # Calculate highest access level for menus
        menu_access_level = UserRoleService._calculate_highest_access(menu_perms)
        
        db_permission = UserRolePermission(
            user_role_id=permission_data["user_role_id"],
            userrole_basic_id=permission_data["userrole_basic_id"],
            menu_permissions=menu_perms,
            # form_permissions removed
            menu_access=menu_access_level,
            # form_access removed
        )
        db.add(db_permission)
        db.commit()
        db.refresh(db_permission)
        return db_permission

    @staticmethod
    def update_user_role_permission(
        db: Session,
        permission_id: UUID,
        update_data: Dict[str, Any]
    ) -> Optional[UserRolePermission]:
        """Update a user role permission from dict data"""
        db_permission = db.query(UserRolePermission).filter(
            UserRolePermission.id == permission_id
        ).first()
        
        if not db_permission:
            return None
        
        # Form permissions removed - not needed
        
        # Convert menu_permissions if present
        if "menu_permissions" in update_data:
            menu_perms = []
            for item in (update_data["menu_permissions"] or []):
                if isinstance(item, dict):
                    perm_dict = {"id": item.get("id")}
                    if item.get("application_id"):
                        perm_dict["application_id"] = item["application_id"]
                    if item.get("modules_id"):
                        perm_dict["modules_id"] = item["modules_id"]
                    if item.get("menu_access"):
                        perm_dict["access"] = item["menu_access"]
                    menu_perms.append(perm_dict)
                else:
                    # Handle Pydantic model
                    perm_dict = {"id": item.id}
                    if hasattr(item, 'application_id') and item.application_id:
                        perm_dict["application_id"] = item.application_id
                    if hasattr(item, 'modules_id') and item.modules_id:
                        perm_dict["modules_id"] = item.modules_id
                    if hasattr(item, 'menu_access') and item.menu_access:
                        perm_dict["access"] = item.menu_access
                    menu_perms.append(perm_dict)
            
            db_permission.menu_permissions = menu_perms
            db_permission.menu_access = UserRoleService._calculate_highest_access(menu_perms)
        
        db.commit()
        db.refresh(db_permission)
        return db_permission

