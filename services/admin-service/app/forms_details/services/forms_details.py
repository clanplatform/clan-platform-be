from typing import Dict, List, Optional, Any
from datetime import datetime
from app.infrastructure.mongodb.mongodb_forms import BaseMongoService

class FormsDetailsService(BaseMongoService):
    """Service for managing form details in MongoDB (hybrid storage with PostgreSQL)
    
    New Structure: Forms are grouped by menu_id
    {
        "menu_id": "uuid",
        "name": "form collection name",
        "access": ["read", "write"],
        "forms": [array of form items]
    }
    """
    
    def __init__(self):
        super().__init__("forms_details")
    
    async def create_or_update_form_collection(
        self,
        menu_id: str,
        collection_name: str,
        access: List[str],
        form_item: Dict[str, Any],
        created_by: Optional[str] = None
    ) -> str:
        """Create or update a form collection for a menu
        
        New structure groups forms by menu_id:
        {
            "menu_id": "uuid",
            "name": "form collection name",
            "access": ["read", "write"],
            "forms": [array of form items]
        }
        """
        collection = await self.get_collection()
        
        # Check if collection exists for this menu
        existing = await collection.find_one({"menu_id": menu_id})
        
        if existing:
            # Add form to existing collection
            result = await collection.update_one(
                {"menu_id": menu_id},
                {
                    "$push": {"forms": form_item},
                    "$set": {
                        "updated_at": datetime.utcnow(),
                        "updated_by": created_by
                    }
                }
            )
            return str(existing["_id"])
        else:
            # Create new collection - use menu_id as collection identifier since name is in forms
            data = {
                "menu_id": menu_id,
                "access": access or ["read", "write"],
                "forms": [form_item],
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "created_by": created_by
            }
            # Only add name if provided (for backward compatibility)
            if collection_name:
                data["name"] = collection_name
            return await self.create(data)
    
    def _ensure_access_field_recursive(self, component: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively ensure access field exists in component and all nested children"""
        if not isinstance(component, dict):
            return component
        
        # Ensure access field exists at current level
        if "access" not in component:
            component["access"] = []
        
        # Process children recursively
        if "children" in component and isinstance(component["children"], list):
            component["children"] = [
                self._ensure_access_field_recursive(child) 
                for child in component["children"]
            ]
        
        return component
    
    async def create_form_details(
        self,
        form_id: str,
        menu_id: str,
        name: str,
        version: str = "1.0.0",
        trigger_when: Optional[str] = None,
        forms: Optional[List[Dict[str, Any]]] = None,
        actions: Optional[Dict[str, Any]] = None,
        modal_type: str = "AntModalAdapter",
        tooltip_type: str = "AntTooltip",
        error_type: str = "AntErrorMessage",
        localization: Optional[Dict[str, Any]] = None,
        languages: Optional[List[Dict[str, Any]]] = None,
        default_language: str = "en-US",
        is_active: bool = True,
        created_by: Optional[str] = None
    ) -> str:
        """Create form details in MongoDB using new grouped structure - clean format only"""
        
        # Prepare the clean form item to add to the collection
        if forms is None or len(forms) == 0:
            # Create default form structure
            form_item = {
                "form_id": form_id,  # Always include form_id
                "name": name,  # Include name in the form object
                "defaultLanguage": default_language or "en-US",
                "form": {
                    "key": "Screen",
                    "type": "Screen",
                    "props": {},
                    "access": [],
                    "children": []
                },
                "languages": languages or [
                    {
                        "code": "en",
                        "dialect": "US",
                        "name": "English",
                        "description": "American English",
                        "bidi": "ltr"
                    }
                ],
                "localization": localization or {},
                "modalType": modal_type or "AntModal",
                "tooltipType": tooltip_type or "AntTooltip",
                "errorType": error_type or "AntErrorMessage",
                "triggerWhen": {},
                "version": version or "1"
            }
        else:
            # Use the first form from the frontend forms array and ensure it's clean
            first_form = forms[0] if isinstance(forms, list) and len(forms) > 0 else {}
            
            # Get name from the form item itself, fallback to parameter
            form_name = first_form.get("name", name)
            
            # Get form structure and ensure access fields at all levels
            form_structure = first_form.get("form", {
                "key": "Screen",
                "type": "Screen", 
                "props": {},
                "access": [],
                "children": []
            })
            
            # Ensure access field exists at form level
            if "access" not in form_structure:
                form_structure["access"] = []
            
            # Recursively ensure access field in all children
            if "children" in form_structure and isinstance(form_structure["children"], list):
                form_structure["children"] = [
                    self._ensure_access_field_recursive(child)
                    for child in form_structure["children"]
                ]
            
            # Create clean form item with form_id - avoid duplicate nesting
            form_item = {
                "form_id": form_id,  # Always ensure form_id is set
                "name": form_name,  # Use name from form item or fallback
                "defaultLanguage": first_form.get("defaultLanguage", default_language or "en-US"),
                "form": form_structure,
                "languages": first_form.get("languages", languages or [
                    {
                        "code": "en",
                        "dialect": "US",
                        "name": "English",
                        "description": "American English",
                        "bidi": "ltr"
                    }
                ]),
                "localization": first_form.get("localization", localization or {}),
                "modalType": first_form.get("modalType", modal_type or "AntModal"),
                "tooltipType": first_form.get("tooltipType", tooltip_type or "AntTooltip"),
                "errorType": first_form.get("errorType", error_type or "AntErrorMessage"),
                "triggerWhen": first_form.get("triggerWhen", {}),
                "version": first_form.get("version", version or "1")
            }
        
        print(f"DEBUG: Creating clean form item with form_id: {form_id}")
        print(f"DEBUG: Form item keys: {list(form_item.keys())}")
        
        # Use the new grouped structure - don't store name at collection level
        return await self.create_or_update_form_collection(
            menu_id=menu_id,
            collection_name="",  # Empty since name is now in form objects
            access=["read", "write"],
            form_item=form_item,
            created_by=created_by
        )
    
    async def update_form_details(self, form_id: str, update_data: Dict[str, Any]) -> bool:
        """Update form details in MongoDB - updates specific form in collection"""
        
        update_data = dict(update_data or {})
        update_data["updated_at"] = datetime.utcnow()
        
        # Ensure access field exists in form structure if present
        if "form" in update_data and isinstance(update_data["form"], dict):
            if "access" not in update_data["form"]:
                update_data["form"]["access"] = []
            
            # Recursively ensure access field in all children
            if "children" in update_data["form"] and isinstance(update_data["form"]["children"], list):
                update_data["form"]["children"] = [
                    self._ensure_access_field_recursive(child)
                    for child in update_data["form"]["children"]
                ]
        
        collection = await self.get_collection()
        
        # Find the collection containing this form and update it
        # This is a placeholder - in new structure we need menu_id to update
        result = await collection.update_one(
            {"forms.form_id": form_id},
            {
                "$set": {
                    "forms.$[elem]": update_data,
                    "updated_at": datetime.utcnow()
                }
            },
            array_filters=[{"elem.form_id": form_id}]
        )
        
        return result.modified_count > 0
    
    async def get_form_details(self, form_id: str) -> Optional[Dict[str, Any]]:
        """Get form details document by form_id reference - searches within forms array"""
        
        collection = await self.get_collection()
        
        # Find collection containing this form
        doc = await collection.find_one({
            "forms.form_id": form_id
        })
        
        if not doc:
            return None
            
        # Extract the specific form from the forms array
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
            
        # Find and return the specific form
        for form in doc.get("forms", []):
            if isinstance(form, dict) and form.get("form_id") == form_id:
                return {
                    "menu_id": doc.get("menu_id"),
                    "collection_name": doc.get("name"),
                    "access": doc.get("access", []),
                    "form": form
                }
        
        return None
    
    async def get_form_details_by_menu(self, menu_id: str) -> Optional[Dict[str, Any]]:
        """Get form collection for a menu_id
        
        Returns the complete collection structure:
        {
            "menu_id": "uuid",
            "name": "form collection name",
            "access": ["read", "write"],
            "forms": [array of form items]
        }
        """
        
        collection = await self.get_collection()
        doc = await collection.find_one({"menu_id": menu_id})
        
        if doc and "_id" in doc:
            doc["_id"] = str(doc["_id"])
        
        return doc
    
    async def delete_form_details(self, form_id: str, menu_id: str) -> bool:
        """Remove a form from the collection"""
        
        collection = await self.get_collection()
        
        # Remove the form from the forms array
        result = await collection.update_one(
            {"menu_id": menu_id},
            {
                "$pull": {"forms": {"form_id": form_id}},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        
        return result.modified_count > 0
    
    async def search_forms_by_component_type(self, component_type: str, menu_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search form collections that contain a specific component type"""
        
        collection = await self.get_collection()
        
        # Build query - search in nested forms array
        query = {
            "forms.form.children.type": component_type
        }
        
        if menu_id:
            query["menu_id"] = menu_id
        
        cursor = collection.find(query).sort("name", 1)
        
        docs = await cursor.to_list(length=None)
        for d in docs:
            if "_id" in d:
                d["_id"] = str(d["_id"])
        return docs
    
    async def search_forms_by_access_level(self, access_level: str, menu_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search form collections that have specific access level"""
        
        collection = await self.get_collection()
        
        # Build query to search for access level
        query = {
            "$or": [
                {"access": access_level},  # Collection level access
                {"forms.form.children.access": access_level}  # Component level access
            ]
        }
        
        if menu_id:
            query["menu_id"] = menu_id
        
        cursor = collection.find(query).sort("name", 1)
        
        docs = await cursor.to_list(length=None)
        for d in docs:
            if "_id" in d:
                d["_id"] = str(d["_id"])
        return docs
    
    async def get_form_components_with_access(self, form_id: str) -> Dict[str, Any]:
        """Get form components with their access permissions"""
        
        collection = await self.get_collection()
        
        # Find collection containing this form
        doc = await collection.find_one({"forms.form_id": form_id})
        
        if not doc:
            return {}
        
        def extract_component_access(components, parent_key=""):
            """Recursively extract component access permissions"""
            access_map = {}
            
            if not isinstance(components, list):
                return access_map
            
            for component in components:
                if not isinstance(component, dict):
                    continue
                
                key = component.get("key", "")
                component_type = component.get("type", "")
                access = component.get("access", [])
                
                full_key = f"{parent_key}.{key}" if parent_key else key
                
                access_map[full_key] = {
                    "type": component_type,
                    "access": access,
                    "read": "read" in access if access else True,
                    "write": "write" in access if access else True,
                    "disable": "disable" in access if access else False
                }
                
                # Process children recursively
                children = component.get("children", [])
                if children:
                    child_access = extract_component_access(children, full_key)
                    access_map.update(child_access)
            
            return access_map
        
        # Find the specific form in the forms array
        forms = doc.get("forms", [])
        result = {
            "form_id": form_id,
            "collection_access": doc.get("access", []),
            "forms": []
        }
        
        # Process each form in the forms array
        for form_item in forms:
            if isinstance(form_item, dict) and 'form' in form_item:
                form = form_item['form']
                form_access = form.get("access", [])
                components = form.get("children", [])
                
                result["forms"].append({
                    "form_access": {
                        "access": form_access,
                        "read": "read" in form_access if form_access else True,
                        "write": "write" in form_access if form_access else True,
                        "disable": "disable" in form_access if form_access else False
                    },
                    "components": extract_component_access(components)
                })
        
        return result
    
    async def update_component_access(
        self, 
        form_id: str, 
        component_key: str, 
        access_permissions: List[str]
    ) -> bool:
        """Update access permissions for a specific component"""
        
        collection = await self.get_collection()
        
        # Update component access using MongoDB array filters
        result = await collection.update_one(
            {"forms.form_id": form_id},
            {"$set": {
                "forms.$[].form.children.$[elem].access": access_permissions,
                "updated_at": datetime.utcnow()
            }},
            array_filters=[{"elem.key": component_key}]
        )
        
        return result.modified_count > 0
    
    async def get_forms_statistics(self, menu_id: Optional[str] = None) -> Dict[str, Any]:
        """Get forms statistics from MongoDB"""
        
        collection = await self.get_collection()
        
        # Build match stage
        match_stage = {}
        if menu_id:
            match_stage["menu_id"] = menu_id
        
        # Aggregation pipeline
        pipeline = [
            {"$match": match_stage},
            {
                "$project": {
                    "menu_id": 1,
                    "total_forms_in_collection": {"$size": "$forms"},
                    "form_types": "$forms.form.type",
                    "component_types": "$forms.form.children.type"
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_collections": {"$sum": 1},
                    "total_forms": {"$sum": "$total_forms_in_collection"},
                    "form_types": {"$addToSet": "$form_types"},
                    "component_types": {"$addToSet": "$component_types"}
                }
            }
        ]
        
        cursor = collection.aggregate(pipeline)
        result = await cursor.to_list(length=1)
        
        if result:
            stats = result[0]
            return {
                "total_collections": stats.get("total_collections", 0),
                "total_forms": stats.get("total_forms", 0),
                "unique_form_types": len(stats.get("form_types", [])),
                "unique_component_types": len([t for sublist in stats.get("component_types", []) for t in (sublist if isinstance(sublist, list) else [sublist])]),
                "menu_id": menu_id
            }
        
        return {
            "total_collections": 0,
            "total_forms": 0,
            "unique_form_types": 0,
            "unique_component_types": 0,
            "menu_id": menu_id
        }
    
    async def create_indexes(self):
        """Create indexes for performance"""
        
        collection = await self.get_collection()
        await collection.create_index("menu_id", unique=True)  # One collection per menu
        await collection.create_index("name")
        await collection.create_index("access")
        await collection.create_index("forms.form_id")  # Index on form IDs within collections
        await collection.create_index("forms.form.type")  # Index on form type
        await collection.create_index("forms.form.children.type")  # Index on component types
        await collection.create_index("forms.form.children.access")  # Index on component access
        
        print("MongoDB forms_details indexes created successfully")

# Global instance
forms_details_service = FormsDetailsService()