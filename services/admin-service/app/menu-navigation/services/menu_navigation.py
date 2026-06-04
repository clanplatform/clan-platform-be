# app/services/navigation_service.py

from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from uuid import UUID
import hashlib
import json
import logging
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.navigation_repository import NavigationRepository
from app.repositories.menu_repository import MenuRepository
from app.schemas.navigation import (
    NavigationStructureSchema,
    NavigationUpdateSchema,
    NavigationResponseSchema,
    NavigationImportSchema
)

logger = logging.getLogger(__name__)

class NavigationService:
    """
    Service for managing navigation structures and their synchronization with the menu system.
    Handles business logic for navigation data including mainNavigation, profileSection, and config.
    """
    
    def __init__(self, database: AsyncIOMotorDatabase, pg_session_factory):
        self.database = database
        self.pg_session_factory = pg_session_factory
        self._navigation_repo: Optional[NavigationRepository] = None
        self._menu_repo: Optional[MenuRepository] = None
    
    @property
    async def navigation_repo(self) -> NavigationRepository:
        """Lazy initialization of navigation repository"""
        if not self._navigation_repo:
            self._navigation_repo = NavigationRepository(self.database)
            await self._navigation_repo.initialize()
        return self._navigation_repo
    
    @property
    async def menu_repo(self) -> MenuRepository:
        """Lazy initialization of menu repository"""
        if not self._menu_repo:
            from app.repositories.menu_repository import MenuRepository
            self._menu_repo = MenuRepository(self.pg_session_factory)
        return self._menu_repo
    
    def generate_data_hash(self, navigation_data: Dict[str, Any]) -> str:
        """
        Generate a hash of the navigation data for change detection
        Excludes metadata fields that change frequently
        """
        # Create a copy and remove metadata fields
        data_copy = navigation_data.copy()
        if "metadata" in data_copy:
            del data_copy["metadata"]
        if "_id" in data_copy:
            del data_copy["_id"]
        
        # Sort keys for consistent hashing
        data_str = json.dumps(data_copy, sort_keys=True, default=str)
        return hashlib.sha256(data_str.encode()).hexdigest()[:16]
    
    async def get_navigation_structure(self, application_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get complete navigation structure for an application
        
        Args:
            application_id: UUID of the application
            
        Returns:
            Complete navigation structure or None if not found
        """
        try:
            repo = await self.navigation_repo
            navigation = await repo.find_by_application_id(application_id)
            
            if navigation:
                # Ensure all required sections are present
                navigation.setdefault("mainNavigation", [])
                navigation.setdefault("profileSection", {
                    "type": "profile",
                    "key": "profile-section",
                    "userData": {
                        "name": "Default User",
                        "email": "user@example.com",
                        "avatar": "",
                        "role": "User",
                        "status": "online"
                    },
                    "menuItems": []
                })
                navigation.setdefault("config", {
                    "version": "1.0.0",
                    "lastUpdated": datetime.utcnow().isoformat(),
                    "theme": "light",
                    "mode": "inline",
                    "collapsible": True,
                    "selectable": True,
                    "multiple": False
                })
            
            return navigation
            
        except Exception as e:
            logger.error(f"Error getting navigation structure for application {application_id}: {e}")
            raise
    
    async def create_navigation_structure(
        self,
        application_id: UUID,
        navigation_data: NavigationStructureSchema,
        created_by: Optional[str] = None
    ) -> str:
        """
        Create a new navigation structure
        
        Args:
            application_id: UUID of the application
            navigation_data: Navigation structure data
            created_by: User who created this structure
            
        Returns:
            ID of the created navigation structure
        """
        try:
            # Prepare the data
            data_dict = navigation_data.dict()
            data_dict["application_id"] = str(application_id)
            data_dict["metadata"] = {"created_by": created_by}
            
            # Generate data hash for change detection
            data_hash = self.generate_data_hash(data_dict)
            data_dict["config"]["dataHash"] = data_hash
            data_dict["config"]["lastUpdated"] = datetime.utcnow().isoformat()
            
            # Create in MongoDB
            repo = await self.navigation_repo
            navigation_id = await repo.create(data_dict)
            
            # Sync with menu system
            await self.sync_menu_hierarchy(application_id, data_dict)
            
            logger.info(f"Created navigation structure for application {application_id}")
            return navigation_id
            
        except Exception as e:
            logger.error(f"Error creating navigation structure: {e}")
            raise
    
    async def update_navigation_structure(
        self,
        application_id: UUID,
        navigation_data: Union[NavigationStructureSchema, NavigationUpdateSchema],
        updated_by: Optional[str] = None
    ) -> bool:
        """
        Update an existing navigation structure
        
        Args:
            application_id: UUID of the application
            navigation_data: Updated navigation data
            updated_by: User who updated this structure
            
        Returns:
            True if update was successful
        """
        try:
            # Get existing navigation to get its ID
            repo = await self.navigation_repo
            existing = await repo.find_by_application_id(application_id)
            
            if not existing:
                raise ValueError(f"Navigation structure not found for application {application_id}")
            
            # Prepare update data
            update_dict = navigation_data.dict(exclude_unset=True)
            update_dict["metadata"] = {"updated_by": updated_by}
            
            # Generate new data hash
            # Merge with existing data for hashing
            merged_data = {**existing, **update_dict}
            data_hash = self.generate_data_hash(merged_data)
            
            # Update config
            if "config" not in update_dict:
                update_dict["config"] = {}
            update_dict["config"]["dataHash"] = data_hash
            update_dict["config"]["lastUpdated"] = datetime.utcnow().isoformat()
            
            # Update in MongoDB
            success = await repo.update(existing["id"], update_dict)
            
            if success:
                # Sync with menu system
                updated_navigation = {**existing, **update_dict}
                await self.sync_menu_hierarchy(application_id, updated_navigation)
                
                logger.info(f"Updated navigation structure for application {application_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error updating navigation structure: {e}")
            raise
    
    async def delete_navigation_structure(self, application_id: UUID, deleted_by: Optional[str] = None) -> bool:
        """
        Delete a navigation structure (soft delete)
        
        Args:
            application_id: UUID of the application
            deleted_by: User who deleted this structure
            
        Returns:
            True if deletion was successful
        """
        try:
            repo = await self.navigation_repo
            existing = await repo.find_by_application_id(application_id)
            
            if not existing:
                raise ValueError(f"Navigation structure not found for application {application_id}")
            
            # Perform soft delete
            success = await repo.delete(existing["id"], soft_delete=True)
            
            if success:
                logger.info(f"Deleted navigation structure for application {application_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error deleting navigation structure: {e}")
            raise
    
    async def sync_menu_hierarchy(self, application_id: UUID, navigation_data: Dict[str, Any]):
        """
        Synchronize navigation structure with the existing menu system
        This creates/updates menu items in PostgreSQL and their details in MongoDB
        
        Args:
            application_id: UUID of the application
            navigation_data: Complete navigation structure data
        """
        try:
            logger.info(f"Syncing menu hierarchy for application {application_id}")
            
            menu_repo = await self.menu_repo

            # Process mainNavigation items
            main_nav = navigation_data.get("mainNavigation", [])

            for menu_item in main_nav:
                await self._process_menu_item(menu_item, application_id, None, menu_repo)
            
            logger.info(f"Menu hierarchy sync completed for application {application_id}")
            
        except Exception as e:
            logger.error(f"Error syncing menu hierarchy: {e}")
            # Don't fail the entire operation if sync fails
            # The navigation structure is still valid
    
    async def _process_menu_item(self, menu_item: Dict[str, Any], application_id: UUID, parent_id: Optional[UUID], menu_repo):
        """
        Process a single menu item and its children
        
        Args:
            menu_item: Menu item data
            application_id: Application UUID
            parent_id: Parent menu ID (if any)
            menu_repo: Menu repository instance
        """
        try:
            # Prepare menu data for PostgreSQL
            menu_data = {
                "application_id": application_id,
                "parent_menu_id": parent_id,
                "name": menu_item["key"],
                "display_name": menu_item["label"],
                "description": menu_item.get("description", ""),
                "icon": menu_item.get("icon", ""),
                "order_index": menu_item.get("order_index", 0),
                "level": menu_item.get("level", 1),
                "is_visible": menu_item.get("is_visible", True),
                "route": menu_item.get("route", ""),
                "component": menu_item.get("component", ""),
                "is_active": True
            }
            
            # Create or update menu in PostgreSQL
            menu_id = await menu_repo.create_menu_with_details(menu_data)
            
            # Create menu details in MongoDB
            details_data = {
                "menu_id": menu_id,
                "application_id": application_id,
                "menu_metadata": menu_item.get("menu_metadata", {}),
                "badge": menu_item.get("badge"),
                "section_title": menu_item.get("sectionTitle"),
                "children_keys": [child["key"] for child in menu_item.get("children", [])]
            }
            
            await menu_repo.create_menu_details(details_data)
            
            # Process children recursively
            for child in menu_item.get("children", []):
                await self._process_menu_item(child, application_id, menu_id, menu_repo)
                
        except Exception as e:
            logger.error(f"Error processing menu item {menu_item.get('key', 'unknown')}: {e}")
            raise
    
    async def import_navigation_structure(self, import_data: NavigationImportSchema, imported_by: Optional[str] = None) -> Dict[str, Any]:
        """
        Import navigation structure from external data
        
        Args:
            import_data: Navigation import data
            imported_by: User who imported this structure
            
        Returns:
            Import result with status and details
        """
        try:
            application_id = import_data.application_id
            navigation_data = import_data.navigation_data
            
            # Check if navigation already exists
            existing = await self.get_navigation_structure(application_id)
            
            if existing and not import_data.overwrite:
                return {
                    "success": False,
                    "message": "Navigation structure already exists. Use overwrite=True to replace.",
                    "existing_version": existing.get("config", {}).get("version")
                }
            
            # Import the navigation structure
            if existing:
                # Update existing
                success = await self.update_navigation_structure(
                    application_id,
                    navigation_data,
                    imported_by
                )
                operation = "updated"
            else:
                # Create new
                navigation_id = await self.create_navigation_structure(
                    application_id,
                    navigation_data,
                    imported_by
                )
                success = bool(navigation_id)
                operation = "created"
            
            if success:
                return {
                    "success": True,
                    "message": f"Navigation structure successfully {operation}",
                    "operation": operation,
                    "version": navigation_data.config.version,
                    "application_id": str(application_id)
                }
            else:
                return {
                    "success": False,
                    "message": f"Failed to {operation} navigation structure",
                    "operation": operation
                }
                
        except Exception as e:
            logger.error(f"Error importing navigation structure: {e}")
            return {
                "success": False,
                "message": f"Import failed: {str(e)}"
            }
    
    async def export_navigation_structure(self, application_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Export navigation structure for backup or migration
        
        Args:
            application_id: UUID of the application
            
        Returns:
            Navigation structure data suitable for export, or None if not found
        """
        try:
            navigation = await self.get_navigation_structure(application_id)
            
            if not navigation:
                return None
            
            # Remove internal fields that shouldn't be exported
            export_data = navigation.copy()
            export_data.pop("id", None)
            export_data.pop("_id", None)
            export_data.pop("metadata", None)
            
            # Ensure application_id is a string
            export_data["application_id"] = str(application_id)
            
            return export_data
            
        except Exception as e:
            logger.error(f"Error exporting navigation structure: {e}")
            raise
    
    async def validate_navigation_structure(self, navigation_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate navigation structure data
        
        Args:
            navigation_data: Navigation structure to validate
            
        Returns:
            Validation result with status and any errors
        """
        try:
            errors = []
            
            # Validate mainNavigation
            if "mainNavigation" not in navigation_data:
                errors.append("mainNavigation is required")
            elif not isinstance(navigation_data["mainNavigation"], list):
                errors.append("mainNavigation must be an array")
            elif len(navigation_data["mainNavigation"]) == 0:
                errors.append("mainNavigation cannot be empty")
            
            # Validate profileSection
            if "profileSection" not in navigation_data:
                errors.append("profileSection is required")
            elif navigation_data["profileSection"].get("type") != "profile":
                errors.append("profileSection type must be 'profile'")
            
            # Validate config
            if "config" not in navigation_data:
                errors.append("config is required")
            else:
                config = navigation_data["config"]
                if "version" not in config:
                    errors.append("config.version is required")
                elif not isinstance(config["version"], str):
                    errors.append("config.version must be a string")
            
            # Validate menu items recursively
            def validate_menu_items(items: List[Dict[str, Any]], path: str = ""):
                for i, item in enumerate(items):
                    current_path = f"{path}[{i}]"
                    
                    if "key" not in item:
                        errors.append(f"{current_path}.key is required")
                    if "label" not in item:
                        errors.append(f"{current_path}.label is required")
                    
                    # Validate children recursively
                    if "children" in item and isinstance(item["children"], list):
                        validate_menu_items(item["children"], f"{current_path}.children")
            
            if "mainNavigation" in navigation_data and isinstance(navigation_data["mainNavigation"], list):
                validate_menu_items(navigation_data["mainNavigation"], "mainNavigation")
            
            return {
                "valid": len(errors) == 0,
                "errors": errors,
                "error_count": len(errors)
            }
            
        except Exception as e:
            logger.error(f"Error validating navigation structure: {e}")
            return {
                "valid": False,
                "errors": [f"Validation error: {str(e)}"],
                "error_count": 1
            }