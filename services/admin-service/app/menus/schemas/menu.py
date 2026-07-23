from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime
from uuid import UUID

from app.core.access import normalize_access as _normalize_access


class BadgeConfig(BaseModel):
    """Badge configuration with count and color of badge"""
    count: Union[int, str] = Field(..., description="Badge count or text")
    color: str = Field(default="blue", description="Badge color")


class MenuBase(BaseModel):
    application_id: UUID = Field(..., description="Application ID this menu belongs to")
    module_id: Optional[UUID] = Field(None, description="Module ID this menu belongs to (Level 2 in hierarchy)")
    name: str = Field(..., min_length=1, max_length=100, description="Menu name")
    key: Optional[str] = Field(None, max_length=100, description="Menu key (unique identifier for navigation)")
    section_title: Optional[str] = Field(None, max_length=200, description="Section title for grouping")
    description: Optional[str] = Field(None, alias="menus_description", description="Menu description")
    label: Optional[str] = Field(None, description="Menu label")
    route: Optional[str] = Field(None, description="Menu route path")
    badge: Optional[Union[str, Dict[str, Any], BadgeConfig]] = Field(
        None, 
        description="Menu badge - can be a string or object with count and color (e.g., {'count': 'NEW', 'color': 'gold'})"
    )
    component: Optional[str] = Field(None, description="Frontend component name")
    icon: Optional[str] = Field(None, description="Menu icon")
    order_index: Optional[int] = Field(0, description="Ordering index for menu display")
    level: Optional[int] = Field(3, description="Menu hierarchy level (Application=1, Module=2, Menu=3, Children=4)")
    is_visible: Optional[bool] = Field(True, description="Whether the menu is visible")
    parent_menu_id: Optional[UUID] = Field(None, description="Parent menu ID for hierarchy", json_schema_extra={"example": None})
    menu_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Menu metadata")
    is_active: Optional[bool] = Field(True, description="Whether the menu is active")
    showtopbar: Optional[bool] = Field(True)
    showsidebar: Optional[bool] = Field(True)

    # ✅ Access permission field (root level - always has a value)
    # Array of strings to support multiple access permissions
    access: List[str] = Field(
        default=["write"],
        description="Access permissions for this menu (e.g., ['read', 'write', 'disable'])"
    )

    
    



class MenuCreate(MenuBase):
    # Accept nested children from modal submissions; each child mirrors navigation item shape
    children: List[Dict[str, Any]] = Field(default_factory=list, description="Nested child items for this menu", json_schema_extra={"example": []})

    @field_validator("access")
    @classmethod
    def validate_access(cls, v):
        return _normalize_access(v)


class MenuBatchCreate(BaseModel):
    """Schema for creating multiple parent menus with nested children in one request"""
    application_id: UUID = Field(..., description="Application ID for all menus")
    module_id: Optional[UUID] = Field(None, description="Module ID for all menus (optional)")
    menus: List[Dict[str, Any]] = Field(..., description="Array of parent menus with their nested children")
    
    model_config = ConfigDict(from_attributes=True)

class MenuUpdate(BaseModel):
    application_id: Optional[UUID] = Field(None, description="Application ID this menu belongs to")
    module_id: Optional[UUID] = Field(None, description="Module ID this menu belongs to")
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Menu name")
    label: Optional[str] = Field(None, description="Menu label")
    route: Optional[str] = Field(None, description="Menu route path")
    component: Optional[str] = Field(None, description="Frontend component name")
    icon: Optional[str] = Field(None, description="Menu icon")
    order_index: Optional[int] = Field(None, description="Ordering index for menu display")
    level: Optional[int] = Field(None, description="Menu hierarchy level")
    is_visible: Optional[bool] = Field(None, description="Whether the menu is visible")
    parent_menu_id: Optional[UUID] = Field(None, description="Parent menu ID for hierarchy")
    is_active: Optional[bool] = Field(None, description="Whether the menu is active")
    showtopbar: Optional[bool] = Field(None)
    showsidebar: Optional[bool] = Field(None)

    # ✅ Access permission can be updated
    # Array of strings to support multiple access permissions
    access: Optional[List[str]] = Field(
        None,
        description="Access permissions (e.g., ['read', 'write', 'disable'])"
    )
    key: Optional[str] = Field(None, max_length=100, description="Menu key")
    # ✅ Badge can be either a string or an object with count and color
    badge: Optional[Union[str, Dict[str, Any], BadgeConfig]] = Field(
        None, 
        description="Menu badge - can be a string or object with count and color"
    )
    section_title: Optional[str] = Field(None, max_length=200, description="Section title")
    description: Optional[str] = Field(None, alias="menus_description", description="Menu description")
    

    # ✅ Children can be updated
    children: List[Dict[str, Any]] = Field(default_factory=list, description="Nested child items for this menu", json_schema_extra={"example": []})
    # Note: mongo_id is managed internally and should not be user-editable

    @field_validator("access")
    @classmethod
    def validate_access(cls, v):
        return _normalize_access(v)

    # ✅ New navigation/UI fields can be updated
    

class MenuResponse(MenuBase):
    id: UUID
    application_id: Optional[UUID] = None
    module_id: Optional[UUID] = None  # New: Module ID in response
    mongo_id: Optional[str] = None

    # ✅ Access permission (always has a value for Menu)
    # Array of strings to support multiple access permissions
    access: List[str] = Field(
        default=["write"],
        description="Access permissions"
    )

    # ✅ Children field in response
    children: Optional[List[Dict[str, Any]]] = Field(None, description="Nested child items for this menu")

    # ✅ New navigation/UI fields in response
    key: Optional[str] = None
    # ✅ Badge can be either a string or an object with count and color
    badge: Optional[Union[str, Dict[str, Any], BadgeConfig]] = None
    section_title: Optional[str] = None
    object_id: Optional[str] = None
    description: Optional[str] = Field(None, alias="menus_description")


    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
