from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
import uuid

class ModuleBase(BaseModel):
    application_id: uuid.UUID = Field(..., description="Application ID this module belongs to")
    name: str = Field(..., min_length=1, max_length=100, description="Module name (internal)")
    code: Optional[str] = Field(None, max_length=50, description="Unique identifier code (e.g., CLIENT_MGMT)")
    key: Optional[str] = Field(None, max_length=100, description="Module key (e.g., analytics-module)")
    label: Optional[str] = Field(None, max_length=150, description="Display name (e.g., Analytics Module)")
    section_title: Optional[str] = Field(None, max_length=150, description="Group title in UI")
    description: Optional[str] = Field(None, description="Module description")
    icon: Optional[str] = Field(None, max_length=100, description="Module icon class/name")
    badge: Optional[str] = Field(None, max_length=50, description="Module badge text")
    route: Optional[str] = Field(None, max_length=255, description="Module route path")
    level: Optional[int] = Field(2, description="Hierarchy level")
    order_index: Optional[int] = Field(0, description="Ordering index")
    is_active: Optional[bool] = Field(True, description="Whether the module is active")
    is_public: Optional[bool] = Field(False, description="Whether the module is public")
    access: Optional[List[str]] = Field(default_factory=list, description="Array of access permissions")

class ModuleCreate(ModuleBase):
    pass

class ModuleUpdate(BaseModel):
    application_id: Optional[uuid.UUID] = Field(None, description="Application ID this module belongs to")
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Module name")
    code: Optional[str] = Field(None, max_length=50, description="Unique identifier code")
    key: Optional[str] = Field(None, max_length=100, description="Module key")
    label: Optional[str] = Field(None, max_length=150, description="Display name")
    section_title: Optional[str] = Field(None, max_length=150, description="Group title in UI")
    description: Optional[str] = Field(None, description="Module description")
    icon: Optional[str] = Field(None, max_length=100, description="Module icon")
    badge: Optional[str] = Field(None, max_length=50, description="Module badge")
    route: Optional[str] = Field(None, max_length=255, description="Module route path")
    level: Optional[int] = Field(None, description="Hierarchy level")
    order_index: Optional[int] = Field(None, description="Ordering index")
    is_active: Optional[bool] = Field(None, description="Whether the module is active")
    is_public: Optional[bool] = Field(None, description="Whether the module is public")
    access: Optional[List[str]] = Field(None, description="Array of access permissions")
    updated_by: Optional[int] = Field(None, description="User ID who updated the module")

class ModuleResponse(ModuleBase):
    id: uuid.UUID
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    created_by: Optional[int] = Field(None, description="User ID who created the module")
    updated_by: Optional[int] = Field(None, description="User ID who last updated the module")

    model_config = ConfigDict(from_attributes=True)

class ModuleListResponse(BaseModel):
    modules: list[ModuleResponse]
    total: int
    page: int
    size: int
    total_pages: int

    model_config = ConfigDict(from_attributes=True)