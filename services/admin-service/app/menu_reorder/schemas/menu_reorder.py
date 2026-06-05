"""
Menu Reordering Schemas
Handles drag-and-drop reordering for menus and nested children
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from uuid import UUID


class MenuReorderItem(BaseModel):
    """Single menu or module item with new order"""
    menu_id: Optional[UUID] = Field(None, description="Menu ID (null for module reordering)")
    module_id: Optional[UUID] = Field(None, description="Module ID (required for module reordering, optional for menu reordering)")
    order_index: int = Field(..., description="New order index (1000, 2000, 3000, etc.)")
    parent_menu_id: Optional[UUID] = Field(None, description="Parent menu ID (null for root level or module reordering)")
    level: Optional[int] = Field(None, description="Hierarchy level (1 for applications, 2 for modules, 3+ for menus)")


class MenuBatchUpdateItem(BaseModel):
    """Single menu item with order and field updates"""
    menu_id: UUID = Field(..., description="Menu ID")
    
    # Reordering fields
    order_index: Optional[int] = Field(None, description="New order index (0-based)")
    parent_menu_id: Optional[UUID] = Field(None, description="Parent menu ID (null for root level)")
    module_id: Optional[UUID] = Field(None, description="Module ID from modules table (for reordering within specific module)")
    
    # Menu field updates
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Menu name")
    label: Optional[str] = Field(None, description="Menu label")
    route: Optional[str] = Field(None, description="Menu route path")
    component: Optional[str] = Field(None, description="Frontend component name")
    icon: Optional[str] = Field(None, description="Menu icon")
    level: Optional[int] = Field(None, description="Menu hierarchy level")
    is_visible: Optional[bool] = Field(None, description="Whether the menu is visible")
    is_active: Optional[bool] = Field(None, description="Whether the menu is active")
    menu_metadata: Optional[Dict[str, Any]] = Field(None, description="Menu metadata")
    showtopbar: Optional[bool] = Field(None)
    showsidebar: Optional[bool] = Field(None)
    
    # Access permissions
    access: Optional[List[str]] = Field(None, description="Access permissions (e.g., ['read', 'write', 'disable'])")
    
    # Navigation/UI fields
    key: Optional[str] = Field(None, max_length=100, description="Menu key")
    badge: Optional[str] = Field(None, max_length=50, description="Menu badge text")
    section_title: Optional[str] = Field(None, max_length=200, description="Section title")
    object_id: Optional[str] = Field(None, max_length=100, description="MongoDB object ID reference")
    description: Optional[str] = Field(None, description="Menu description")
    
    # Children updates
    children: Optional[List[Dict[str, Any]]] = Field(None, description="Nested child items for this menu")


class MenuReorderRequest(BaseModel):
    """Request to reorder multiple menus"""
    items: List[MenuReorderItem] = Field(..., description="List of menus with new order")
    application_id: UUID = Field(..., description="Application ID to scope the reordering")


class MenuBatchUpdateRequest(BaseModel):
    """Request to batch update menus (reorder + field updates)"""
    items: List[MenuBatchUpdateItem] = Field(..., description="List of menus with updates")
    application_id: UUID = Field(..., description="Application ID to scope the updates")


class MenuReorderResponse(BaseModel):
    """Response after reordering"""
    message: str = Field(..., description="Success message")
    updated_count: int = Field(..., description="Number of menus updated")
    items: List[MenuReorderItem] = Field(..., description="Updated menu items")


class MenuBatchUpdateResponse(BaseModel):
    """Response after batch update"""
    message: str = Field(..., description="Success message")
    updated_count: int = Field(..., description="Number of menus updated")
    items: List[MenuBatchUpdateItem] = Field(..., description="Updated menu items")


class BulkMenuReorderRequest(BaseModel):
    """Bulk reorder request for parent and all children"""
    application_id: UUID = Field(..., description="Application ID")
    parent_orders: List[MenuReorderItem] = Field(..., description="Parent menu order")
    children_orders: Optional[List[MenuReorderItem]] = Field(None, description="Children menu order")


# Example request body for Swagger documentation
class MenuReorderExample:
    """Example request bodies for documentation"""
    
    SIMPLE_REORDER = {
        "application_id": "2c9539c5-5142-4921-8f4f-35db5b426efa",
        "items": [
            {
                "menu_id": "menu-uuid-1",
                "order_index": 0,
                "parent_menu_id": None,
                "level": 1,
                "module_id": "module-uuid-1"
            },
            {
                "menu_id": "menu-uuid-2",
                "order_index": 1,
                "parent_menu_id": None,
                "level": 1,
                "module_id": "module-uuid-1"
            },
            {
                "menu_id": "menu-uuid-3",
                "order_index": 2,
                "parent_menu_id": None,
                "level": 1,
                "module_id": "module-uuid-2"
            }
        ]
    }
    
    BATCH_UPDATE_WITH_FIELDS = {
        "application_id": "2c9539c5-5142-4921-8f4f-35db5b426efa",
        "items": [
            {
                "menu_id": "menu-uuid-1",
                "order_index": 0,
                "parent_menu_id": None,
                "module_id": "module-uuid-1",
                "name": "dashboard",
                "label": "Dashboard",
                "icon": "ri-dashboard-line",
                "route": "/dashboard",
                "is_visible": True
            },
            {
                "menu_id": "menu-uuid-2",
                "order_index": 1,
                "parent_menu_id": None,
                "module_id": "module-uuid-1",
                "label": "Updated Settings",
                "badge": "New",
                "description": "System settings and configuration"
            }
        ]
    }
    
    NESTED_REORDER = {
        "application_id": "2c9539c5-5142-4921-8f4f-35db5b426efa",
        "items": [
            # Parent menus
            {
                "menu_id": "admin-app-uuid",
                "order_index": 0,
                "parent_menu_id": None
            },
            {
                "menu_id": "calendar-app-uuid",
                "order_index": 1,
                "parent_menu_id": None
            },
            # Children of AdminApp
            {
                "menu_id": "client-setup-uuid",
                "order_index": 0,
                "parent_menu_id": "admin-app-uuid"
            },
            {
                "menu_id": "app-setup-uuid",
                "order_index": 1,
                "parent_menu_id": "admin-app-uuid"
            },
            {
                "menu_id": "user-roles-setup-uuid",
                "order_index": 2,
                "parent_menu_id": "admin-app-uuid"
            },
            # Nested children under Client setup
            {
                "menu_id": "entities-branches-uuid",
                "order_index": 0,
                "parent_menu_id": "client-setup-uuid"
            },
            {
                "menu_id": "date-time-uuid",
                "order_index": 1,
                "parent_menu_id": "client-setup-uuid"
            },
            {
                "menu_id": "divisions-uuid",
                "order_index": 2,
                "parent_menu_id": "client-setup-uuid"
            }
        ]
    }
