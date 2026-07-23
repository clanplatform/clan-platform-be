"""
User Menu Service
Fetches menus based on user's role permissions from userrole_permission table
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Dict, Any, Optional
from uuid import UUID

from app.models.user_setup import UserSetupBasic, UserSetupRolesEntity
from app.models.user_role import UserRolePermission
from app.models.menu import Menu


class UserMenuService:
    """Service for fetching user menus based on role permissions"""

    @staticmethod
    def get_user_menus(db: Session, user_id: UUID) -> List[Dict[str, Any]]:
        """
        Get all menus accessible to a user based on their role permissions
        
        Args:
            db: Database session
            user_id: User's usersetup_basic.id
            
        Returns:
            List of menu dictionaries with access permissions
        """
        # 1. Get user's basic info
        user = db.query(UserSetupBasic).filter(UserSetupBasic.id == user_id).first()
        if not user:
            return []
        
        # 2. Get user's assigned roles from usersetup_roles_entity
        roles_entity = db.query(UserSetupRolesEntity).filter(
            UserSetupRolesEntity.usersetup_basic_id == user_id
        ).first()
        
        if not roles_entity or not roles_entity.assigned_roles:
            return []
        
        assigned_role_ids = roles_entity.assigned_roles
        
        # 3. Get all menu permissions for these roles from userrole_permission
        # Fixed: Check for menu_permissions JSONB field, not menu_id
        menu_permissions = db.query(UserRolePermission).filter(
            and_(
                UserRolePermission.user_role_id.in_(assigned_role_ids),
                UserRolePermission.menu_permissions.isnot(None),
                UserRolePermission.menu_permissions != []
            )
        ).all()
        
        if not menu_permissions:
            return []
        
        # 4. Extract unique menu IDs and their access permissions from JSONB
        menu_access_map = {}
        for perm in menu_permissions:
            # menu_permissions is JSONB: [{"id": "uuid", "access": ["read", "write"]}, ...]
            if perm.menu_permissions:
                for menu_perm in perm.menu_permissions:
                    menu_id = menu_perm.get('id')
                    access_list = menu_perm.get('access', [])
                    
                    if menu_id:
                        if menu_id not in menu_access_map:
                            menu_access_map[menu_id] = set()
                        # Combine access permissions from all roles
                        menu_access_map[menu_id].update(access_list)
        
        if not menu_access_map:
            return []
        
        # 5. Fetch menu details from menus table
        menu_ids = [UUID(mid) for mid in menu_access_map.keys()]
        menus = db.query(Menu).filter(
            and_(
                Menu.id.in_(menu_ids),
                Menu.is_active == True,
                Menu.deleted_at.is_(None)
            )
        ).order_by(Menu.order_index, Menu.level).all()
        
        # 6. Build menu response with access permissions
        menu_list = []
        for menu in menus:
            # Check if user has 'disable' access - if so, skip this menu
            user_access = list(menu_access_map.get(str(menu.id), set()))
            
            if 'disable' in user_access:
                # Menu is disabled for this user, don't include it
                continue
            
            menu_dict = {
                "id": str(menu.id),
                "name": menu.name,
                "label": menu.label,
                "icon": menu.icon,
                "route": menu.route,
                "component": menu.component,
                "parent_menu_id": str(menu.parent_menu_id) if menu.parent_menu_id else None,
                "level": menu.level,
                "order_index": menu.order_index,
                "is_visible": menu.is_visible,
                "user_access": user_access,  # User's specific access permissions
                "can_read": 'read' in user_access,
                "can_write": 'write' in user_access,
            }
            menu_list.append(menu_dict)
        
        return menu_list

    @staticmethod
    def get_user_menu_hierarchy(db: Session, user_id: UUID) -> List[Dict[str, Any]]:
        """
        Get user menus organized in hierarchical structure
        
        Args:
            db: Database session
            user_id: User's usersetup_basic.id
            
        Returns:
            List of root menus with nested children
        """
        # Get flat list of menus
        menus = UserMenuService.get_user_menus(db, user_id)
        
        if not menus:
            return []
        
        # Build hierarchy
        menu_map = {menu['id']: menu for menu in menus}
        root_menus = []
        
        for menu in menus:
            menu['children'] = []
            parent_id = menu.get('parent_menu_id')
            
            if parent_id and parent_id in menu_map:
                # Add to parent's children
                menu_map[parent_id]['children'].append(menu)
            else:
                # Root level menu
                root_menus.append(menu)
        
        return root_menus

    @staticmethod
    def check_menu_access(db: Session, user_id: UUID, menu_id: UUID, required_access: str = 'read') -> bool:
        """
        Check if user has specific access to a menu
        
        Args:
            db: Database session
            user_id: User's usersetup_basic.id
            menu_id: Menu ID to check
            required_access: Required access level ('read', 'write', 'disable')
            
        Returns:
            True if user has the required access, False otherwise
        """
        # Get user's roles
        roles_entity = db.query(UserSetupRolesEntity).filter(
            UserSetupRolesEntity.usersetup_basic_id == user_id
        ).first()
        
        if not roles_entity or not roles_entity.assigned_roles:
            return False
        
        # Check permissions in JSONB menu_permissions field
        permissions = db.query(UserRolePermission).filter(
            and_(
                UserRolePermission.user_role_id.in_(roles_entity.assigned_roles),
                UserRolePermission.menu_permissions.isnot(None)
            )
        ).all()
        
        if not permissions:
            return False
        
        # Search through JSONB menu_permissions for the specific menu
        menu_id_str = str(menu_id)
        for permission in permissions:
            if permission.menu_permissions:
                for menu_perm in permission.menu_permissions:
                    if menu_perm.get('id') == menu_id_str:
                        access_list = menu_perm.get('access', [])
                        return required_access in access_list
        
        return False

