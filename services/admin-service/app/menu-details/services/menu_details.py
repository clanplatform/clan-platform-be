from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.application import Application
from app.models.modules import Module
from .base_mongodb import BaseMongoService

class MenuDetailsService(BaseMongoService):
    """Service for managing menu details in MongoDB (hybrid storage with PostgreSQL)"""
    
    def __init__(self):
        super().__init__("menu_details")
    
    async def create_menu_details(
        self,
        menu_id: str,
        application_id: str,
        module_id: Optional[str] = None,  # New: Module ID for level 2
        route: Optional[str] = None,
        icon: Optional[str] = None,
        order_index: Optional[int] = 0,
        parent_menu_id: Optional[str] = None,
        level: Optional[int] = 3,  # Default to level 3 (menus) since modules are level 2
        is_visible: Optional[bool] = True,
        component: Optional[str] = None,
        menu_metadata: Optional[Dict[str, Any]] = None,
        is_active: Optional[bool] = True,
        showtopbar: Optional[bool] = True,
        showsidebar: Optional[bool] = True,
        # Extended fields for full child-object snapshot and navigation metadata
        key: Optional[str] = None,
        label: Optional[str] = None,
        description: Optional[str] = None,
        badge: Optional[Dict[str, Any]] = None,
        sectionTitle: Optional[str] = None,
        icons: Optional[List[Dict[str, Any]]] = None,
        children: Optional[List[Dict[str, Any]]] = None,
        # Profile/config container support
        type: Optional[str] = None,
        profileSection: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None,
        # Access field support
        access: Optional[List[str]] = None,
    ) -> str:
        """
        Create menu details in MongoDB with 4-level hierarchy support:
        Level 1: Application
        Level 2: Modules
        Level 3: Menus
        Level 4: Nested Children
        Includes access field support for applications and modules.
        """

        if menu_metadata is None:
            menu_metadata = {}

        data = {
            "menu_id": menu_id,
            "application_id": application_id,
            "module_id": module_id,  # New: Module ID for hierarchy
            "route": route,
            "icon": icon,
            "order_index": order_index or 0,
            "parent_menu_id": parent_menu_id,
            "level": level or 3,  # Default to level 3 (menus)
            "is_visible": True if is_visible is None else is_visible,
            "component": component,
            "showtopbar": True if showtopbar is None else showtopbar,
            "showsidebar": True if showsidebar is None else showsidebar,
            "menu_metadata": menu_metadata or {},
            "is_active": True if is_active is None else is_active,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        # Optional navigation metadata (unified structure fields)
        if key is not None:
            data["key"] = key
        if label is not None:
            data["label"] = label
        if description is not None:
            data["description"] = description
        if badge is not None:
            data["badge"] = badge
        if sectionTitle is not None:
            data["sectionTitle"] = sectionTitle
        if icons is not None:
            data["icons"] = icons
        # if children is not None:
        #     data["children"] = children
        if children is not None:
            for child in children:
                child["showtopbar"] = child.get("showtopbar", True)
                child["showsidebar"] = child.get("showsidebar", True)
            data["children"] = children

        # Optional profile/config support
        if type is not None:
            data["type"] = type
        if profileSection is not None:
            data["profileSection"] = profileSection
        if config is not None:
            data["config"] = config
        
        # Access field support
        if access is not None:
            data["access"] = access

        return await self.create(data)
    
    def _get_access_data_from_postgres(self, db: Session, application_id: Optional[str] = None, module_id: Optional[str] = None) -> Dict[str, List[str]]:
        """
        Helper method to fetch access data from PostgreSQL tables
        Returns dict with 'application_access' and 'module_access' keys
        """
        result = {
            "application_access": [],
            "module_access": []
        }
        
        try:
            # Fetch application access
            if application_id:
                pg_app = db.query(Application).filter(
                    Application.id == application_id,
                    Application.is_active == True,
                    Application.is_deleted == False
                ).first()
                if pg_app and pg_app.access:
                    result["application_access"] = pg_app.access
            
            # Fetch module access
            if module_id:
                pg_module = db.query(Module).filter(
                    Module.id == module_id,
                    Module.is_active == True,
                    Module.is_deleted == False
                ).first()
                if pg_module and pg_module.access:
                    result["module_access"] = pg_module.access
        
        except Exception as e:
            print(f"Error fetching access data from PostgreSQL: {e}")
        
        return result
    
    async def update_menu_details(self, menu_id: str, update_data: Dict[str, Any]) -> bool:
        """Update menu details in MongoDB by menu_id reference"""
        
        update_data = dict(update_data or {})
        update_data["updated_at"] = datetime.utcnow()
        
        collection = await self.get_collection()
        result = await collection.update_one(
            {"menu_id": menu_id, "is_active": True},
            {"$set": update_data}
        )
        
        return result.modified_count > 0
    
    async def get_menu_details(self, menu_id: str) -> Optional[Dict[str, Any]]:
        """Get menu details document by menu_id reference"""
        
        collection = await self.get_collection()
        doc = await collection.find_one({
            "menu_id": menu_id,
            "is_active": True
        })
        
        if doc and "_id" in doc:
            doc["_id"] = str(doc["_id"])  # normalize id
        return doc
    
    async def get_menu_details_by_application(self, application_id: str) -> List[Dict[str, Any]]:
        """Get all menu details for an application_id"""
        
        collection = await self.get_collection()
        cursor = collection.find({
            "application_id": application_id,
            "is_active": True
        }).sort("order_index", 1)
        
        docs = await cursor.to_list(length=None)
        for d in docs:
            if "_id" in d:
                d["_id"] = str(d["_id"])  # normalize id
        return docs
    
    async def delete_menu_details(self, menu_id: str) -> bool:
        """Soft delete menu details by menu_id reference"""
        
        collection = await self.get_collection()
        result = await collection.update_one(
            {"menu_id": menu_id, "is_active": True},
            {"$set": {
                "is_active": False,
                "updated_at": datetime.utcnow()
            }}
        )
        
        return result.modified_count > 0
    
    async def get_menu_details_by_module(self, module_id: str) -> List[Dict[str, Any]]:
        """Get all menu details for a specific module_id"""
        
        collection = await self.get_collection()
        cursor = collection.find({
            "module_id": module_id,
            "is_active": True
        }).sort("order_index", 1)
        
        docs = await cursor.to_list(length=None)
        for d in docs:
            if "_id" in d:
                d["_id"] = str(d["_id"])  # normalize id
        return docs
    
    async def get_menu_hierarchy_by_application(self, application_id: str) -> Dict[str, Any]:
        """
        Get complete menu hierarchy for an application with 4-level structure:
        Application -> Modules -> Menus -> Nested Children
        """
        
        collection = await self.get_collection()
        
        # Get all menu details for the application
        cursor = collection.find({
            "application_id": application_id,
            "is_active": True
        }).sort([("level", 1), ("order_index", 1)])
        
        all_menus = await cursor.to_list(length=None)
        
        # Normalize ObjectIds
        for menu in all_menus:
            if "_id" in menu:
                menu["_id"] = str(menu["_id"])
        
        # Organize by hierarchy levels
        hierarchy = {
            "application_id": application_id,
            "modules": {},  # Level 2: Modules
            "orphaned_menus": []  # Menus without modules
        }
        
        # Group by modules first
        for menu in all_menus:
            module_id = menu.get("module_id")
            
            if module_id:
                if module_id not in hierarchy["modules"]:
                    hierarchy["modules"][module_id] = {
                        "module_id": module_id,
                        "menus": [],
                        "nested_children": {}
                    }
                
                if menu.get("level") == 3:  # Level 3: Menus
                    hierarchy["modules"][module_id]["menus"].append(menu)
                elif menu.get("level") == 4:  # Level 4: Nested Children
                    parent_id = menu.get("parent_menu_id")
                    if parent_id:
                        if parent_id not in hierarchy["modules"][module_id]["nested_children"]:
                            hierarchy["modules"][module_id]["nested_children"][parent_id] = []
                        hierarchy["modules"][module_id]["nested_children"][parent_id].append(menu)
            else:
                # Menus without modules (legacy or special cases)
                hierarchy["orphaned_menus"].append(menu)
        
        return hierarchy

    async def get_structured_navigation_hierarchy(self, nav_doc_id: str) -> Dict[str, Any]:
        """
        Get structured navigation hierarchy: Applications -> Modules -> Menus -> Nested Menus
        This method returns the complete 4-level hierarchy for the navigation document.
        Structure: Root Application -> children[Modules] -> children[Menus] -> children[Nested Menus]
        Includes access field from PostgreSQL applications and modules tables.
        """
        from bson import ObjectId
        
        collection = await self.get_collection()
        
        # Get the navigation document
        nav_doc = await collection.find_one({"_id": ObjectId(nav_doc_id)})
        
        if not nav_doc:
            return {"error": "Navigation document not found"}
        
        # Initialize the structured hierarchy
        structured_hierarchy = {
            "_id": str(nav_doc["_id"]),
            "applications": []
        }
        
        # Get mainNavigation array (contains application ObjectIds)
        main_navigation = nav_doc.get("mainNavigation", [])
        
        # Get PostgreSQL session for fetching access data
        from app.db.database import SessionLocal
        db = SessionLocal()
        
        try:
            for app_object_id in main_navigation:
                # Get application document
                app_doc = await collection.find_one({"_id": app_object_id})
                
                if not app_doc:
                    continue
                
                # Fetch access field from PostgreSQL applications table
                app_access = []
                if app_doc.get("application_id"):
                    pg_app = db.query(Application).filter(
                        Application.id == app_doc.get("application_id"),
                        Application.is_active == True,
                        Application.is_deleted == False
                    ).first()
                    if pg_app and pg_app.access:
                        app_access = pg_app.access
                
                # Structure: Application (Level 1) with children = modules
                application = {
                    "_id": str(app_doc["_id"]),
                    "key": app_doc.get("key"),
                    "label": app_doc.get("label"),
                    "icon": app_doc.get("icon"),
                    "description": app_doc.get("description"),
                    "badge": app_doc.get("badge"),
                    "sectionTitle": app_doc.get("sectionTitle"),
                    "route": app_doc.get("route"),
                    "application_id": app_doc.get("application_id"),
                    "level": 1,
                    "access": app_access,  # Access field from PostgreSQL applications table
                    "order_index": app_doc.get("order_index", 1000),
                    "children": []  # This will contain modules (Level 2)
                }
                
                # Process children to organize into modules structure
                children = app_doc.get("children", [])
                modules_map = {}
                
                # First pass: Group menus by module_id
                for child in children:
                    module_id = child.get("module_id")
                    
                    if module_id:
                        # This child belongs to a module
                        if module_id not in modules_map:
                            # Fetch access field from PostgreSQL modules table
                            module_access = []
                            pg_module = db.query(Module).filter(
                                Module.id == module_id,
                                Module.is_active == True,
                                Module.is_deleted == False
                            ).first()
                            if pg_module and pg_module.access:
                                module_access = pg_module.access
                            
                            modules_map[module_id] = {
                                "_id": child.get("moduleObjectId"),
                                "key": child.get("moduleKey", module_id),
                                "label": child.get("moduleLabel", "Module"),
                                "icon": child.get("moduleIcon", "ri-folder-line"),
                                "description": child.get("moduleDescription", ""),
                                "badge": child.get("moduleBadge"),
                                "sectionTitle": child.get("moduleSectionTitle", ""),
                                "route": child.get("moduleRoute", ""),
                                "component": child.get("moduleComponent", ""),
                                "module_id": module_id,
                                "level": 2,
                                "access": module_access,  # Access field from PostgreSQL modules table
                                "order_index": child.get("moduleOrderIndex", 1000),
                                "children": []  # This will contain menus (Level 3)
                            }
                        
                        # Add menu to module's children array
                        menu_item = {
                            "_id": child.get("_id"),
                            "key": child.get("key"),
                            "label": child.get("label"),
                            "icon": child.get("icon"),
                            "description": child.get("description"),
                            "badge": child.get("badge"),
                            "sectionTitle": child.get("sectionTitle"),
                            "route": child.get("route"),
                            "component": child.get("component"),
                            "menu_id": child.get("menu_id"),
                            "module_id": module_id,
                            "level": 3,
                            "order_index": child.get("order_index", 1000),
                            "children": self._process_nested_menus(child.get("children", []))  # Level 4: Nested Menus
                        }
                        
                        modules_map[module_id]["children"].append(menu_item)
                    else:
                        # This is a direct menu without module (legacy support)
                        # Create a default module for orphaned menus
                        if "default" not in modules_map:
                            modules_map["default"] = {
                                "_id": None,
                                "key": "default-module",
                                "label": "Default Module",
                                "icon": "ri-folder-line",
                                "description": "Default module for menus without specific module",
                                "badge": None,
                                "sectionTitle": "Default",
                                "route": "",
                                "component": "",
                                "module_id": "default",
                                "level": 2,
                                "access": [],  # Empty access for default module
                                "order_index": 9999,
                                "children": []
                            }
                        
                        menu_item = {
                            "_id": child.get("_id"),
                            "key": child.get("key"),
                            "label": child.get("label"),
                            "icon": child.get("icon"),
                            "description": child.get("description"),
                            "badge": child.get("badge"),
                            "sectionTitle": child.get("sectionTitle"),
                            "route": child.get("route"),
                            "component": child.get("component"),
                            "menu_id": child.get("menu_id"),
                            "module_id": None,
                            "level": 3,
                            "order_index": child.get("order_index", 1000),
                            "children": self._process_nested_menus(child.get("children", []))
                        }
                        
                        modules_map["default"]["children"].append(menu_item)
                
                # Convert modules_map to sorted list and assign to application children
                application["children"] = sorted(
                    modules_map.values(),
                    key=lambda x: x["order_index"]
                )
                
                structured_hierarchy["applications"].append(application)
        
        finally:
            db.close()
        
        return structured_hierarchy
    
    def _process_nested_menus(self, children: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process nested menus (Level 4) recursively
        """
        nested_menus = []
        
        for child in children:
            nested_menu = {
                "_id": child.get("_id"),
                "key": child.get("key"),
                "label": child.get("label"),
                "icon": child.get("icon"),
                "description": child.get("description"),
                "badge": child.get("badge"),
                "sectionTitle": child.get("sectionTitle"),
                "route": child.get("route"),
                "component": child.get("component"),
                "menu_id": child.get("menu_id"),
                "level": 4,
                "order_index": child.get("order_index", 1000),
                "children": self._process_nested_menus(child.get("children", []))  # Support deeper nesting
            }
            nested_menus.append(nested_menu)
        
        return sorted(nested_menus, key=lambda x: x["order_index"])
    
    async def get_menu_details_by_application_and_module(
        self, 
        application_id: str, 
        module_id: str
    ) -> List[Dict[str, Any]]:
        """Get menu details for a specific application and module combination"""
        
        collection = await self.get_collection()
        cursor = collection.find({
            "application_id": application_id,
            "module_id": module_id,
            "is_active": True
        }).sort("order_index", 1)
        
        docs = await cursor.to_list(length=None)
        for d in docs:
            if "_id" in d:
                d["_id"] = str(d["_id"])  # normalize id
        return docs
    
    async def get_menu_details_by_parent(self, parent_menu_id: str) -> List[Dict[str, Any]]:
        """Get menu details by parent_menu_id reference"""
        
        collection = await self.get_collection()
        cursor = collection.find({
            "parent_menu_id": parent_menu_id,
            "is_active": True
        }).sort("order_index", 1)
        
        docs = await cursor.to_list(length=None)
        for d in docs:
            if "_id" in d:
                d["_id"] = str(d["_id"])  # normalize id
        return docs
    
    async def create_indexes(self):
        """Create indexes for performance with module support"""
        
        collection = await self.get_collection()
        await collection.create_index("menu_id")
        await collection.create_index("application_id")
        await collection.create_index("module_id")  # New: Module index
        await collection.create_index("parent_menu_id")
        await collection.create_index("level")  # New: Level index for hierarchy
        await collection.create_index([("application_id", 1), ("is_active", 1)])
        await collection.create_index([("module_id", 1), ("is_active", 1)])  # New: Module + active
        await collection.create_index([("application_id", 1), ("module_id", 1), ("is_active", 1)])  # New: App + Module + active
        await collection.create_index([("parent_menu_id", 1), ("is_active", 1)])
        await collection.create_index([("level", 1), ("order_index", 1)])  # New: Level + order for hierarchy
        await collection.create_index([("order_index", 1)])
        
        print("MongoDB menu_details indexes created successfully with module support")

    async def get_navigation_with_access_data(self, nav_doc_id: str) -> Dict[str, Any]:
        """
        Get navigation hierarchy with access data from PostgreSQL included at application and module levels.
        This is the main method to use for frontend navigation with access control.
        """
        return await self.get_structured_navigation_hierarchy(nav_doc_id)

# Global instance
menu_details_service = MenuDetailsService()