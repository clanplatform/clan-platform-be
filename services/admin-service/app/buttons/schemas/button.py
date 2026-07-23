from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
import uuid


class ButtonBase(BaseModel):
    menu_id: uuid.UUID = Field(..., description="Menu ID this button belongs to")
    name: str = Field(..., min_length=1, max_length=100, description="Internal button name")
    label: str = Field(..., min_length=1, max_length=150, description="Display label")
    key: Optional[str] = Field(None, max_length=100, description="Unique key for the button")
    icon: Optional[str] = Field(None, max_length=100, description="Icon class/name")
    tooltip: Optional[str] = Field(None, max_length=255, description="Tooltip text")
    variant: Optional[str] = Field(None, max_length=50, description="Visual variant: primary, secondary, danger")
    action_type: Optional[str] = Field(None, max_length=100, description="Action type: submit, reset, navigate, modal")
    action_payload: Optional[Dict[str, Any]] = Field(None, description="Flexible payload for the action")
    order_index: Optional[int] = Field(0, description="Display order within the menu")
    is_active: Optional[bool] = Field(True, description="Whether the button is active")
    is_visible: Optional[bool] = Field(True, description="Whether the button is visible")
    access: Optional[List[str]] = Field(default_factory=lambda: ["read"], description="Access permissions")


class ButtonCreate(ButtonBase):
    pass


class ButtonUpdate(BaseModel):
    menu_id: Optional[uuid.UUID] = Field(None, description="Menu ID this button belongs to")
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Internal button name")
    label: Optional[str] = Field(None, min_length=1, max_length=150, description="Display label")
    key: Optional[str] = Field(None, max_length=100, description="Unique key for the button")
    icon: Optional[str] = Field(None, max_length=100, description="Icon class/name")
    tooltip: Optional[str] = Field(None, max_length=255, description="Tooltip text")
    variant: Optional[str] = Field(None, max_length=50, description="Visual variant")
    action_type: Optional[str] = Field(None, max_length=100, description="Action type")
    action_payload: Optional[Dict[str, Any]] = Field(None, description="Action payload")
    order_index: Optional[int] = Field(None, description="Display order")
    is_active: Optional[bool] = Field(None, description="Whether the button is active")
    is_visible: Optional[bool] = Field(None, description="Whether the button is visible")
    access: Optional[List[str]] = Field(None, description="Access permissions")
    updated_by: Optional[str] = Field(None, description="User who updated the button")


class ButtonResponse(ButtonBase):
    id: uuid.UUID
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ButtonListResponse(BaseModel):
    buttons: List[ButtonResponse]
    total: int
    page: int
    size: int
    total_pages: int

    model_config = ConfigDict(from_attributes=True)
