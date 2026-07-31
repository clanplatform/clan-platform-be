from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime
import uuid

from app.core.access import normalize_access as _normalize_access

class ApplicationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Application name")
    description: Optional[str] = Field(None, description="Application description")
    version: Optional[str] = Field(None, max_length=20, description="Application version")
    status: Optional[str] = Field("active", description="Application status")
    domain_id: uuid.UUID = Field(..., description="Domain ID this application belongs to")
    is_active: Optional[bool] = Field(True, description="Whether the application is active")
    access: Optional[List[str]] = Field(default_factory=list, description="Array of access permissions")

    # ✅ New fields for navigation/UI display
    key: Optional[str] = Field(None, max_length=100, description="Application key (unique identifier for navigation)")
    label: Optional[str] = Field(None, max_length=100, description="Application display label")
    route: Optional[str] = Field(None, max_length=200, description="Application route path")
    level: Optional[int] = Field(1, description="Hierarchy level")
    icon: Optional[str] = Field(None, max_length=100, description="Application icon class/name")
    badge: Optional[str] = Field(None, max_length=50, description="Application badge text")
    section_title: Optional[str] = Field(None, max_length=200, description="Section title for grouping applications")
    order_index: Optional[int] = Field(0, description="Order index for sorting applications")

class ApplicationCreate(ApplicationBase):
    @field_validator("access")
    @classmethod
    def validate_access(cls, v):
        return _normalize_access(v)

class ApplicationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Application name")
    description: Optional[str] = Field(None, description="Application description")
    version: Optional[str] = Field(None, max_length=20, description="Application version")
    status: Optional[str] = Field(None, description="Application status")
    domain_id: Optional[uuid.UUID] = Field(None, description="Domain ID this application belongs to")
    is_active: Optional[bool] = Field(None, description="Whether the application is active")
    access: Optional[List[str]] = Field(None, description="Array of access permissions")

    # ✅ New fields for navigation/UI display
    key: Optional[str] = Field(None, max_length=100, description="Application key")
    label: Optional[str] = Field(None, max_length=100, description="Application label")
    route: Optional[str] = Field(None, max_length=200, description="Application route path")
    level: Optional[int] = Field(None, description="Hierarchy level")
    icon: Optional[str] = Field(None, max_length=100, description="Application icon")
    badge: Optional[str] = Field(None, max_length=50, description="Application badge")
    section_title: Optional[str] = Field(None, max_length=200, description="Section title")
    order_index: Optional[int] = Field(None, description="Order index for sorting applications")

    @field_validator("access")
    @classmethod
    def validate_access(cls, v):
        return _normalize_access(v)

class ApplicationResponse(ApplicationBase):
    id: uuid.UUID
    order_index: int
    created_at: datetime
    updated_at: datetime


# ✅ New schema for application with nested menus
class ApplicationWithMenusResponse(BaseModel):
    """Response schema for application with its menu hierarchy"""
    # Application details
    application_id: uuid.UUID = Field(..., description="Application ID")
    application_name: str = Field(..., description="Application name")
    application_description: Optional[str] = Field(None, description="Application description")
    application_version: Optional[str] = Field(None, description="Application version")
    application_status: Optional[str] = Field(None, description="Application status")
    application_key: Optional[str] = Field(None, description="Application key")
    application_label: Optional[str] = Field(None, description="Application label")
    application_route: Optional[str] = Field(None, description="Application route")
    application_level: Optional[int] = Field(None, description="Application Hierarchy level")
    application_icon: Optional[str] = Field(None, description="Application icon")
    application_badge: Optional[str] = Field(None, description="Application badge")
    application_section_title: Optional[str] = Field(None, description="Application section title")
    application_is_active: bool = Field(..., description="Whether application is active")
    application_created_at: datetime = Field(..., description="Application creation timestamp")
    application_updated_at: datetime = Field(..., description="Application update timestamp")
    
    # Parent menus with nested children
    menus: List[Dict[str, Any]] = Field(default_factory=list, description="Parent menus with nested children")
    
