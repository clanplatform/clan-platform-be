from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
import uuid


class ClientModuleBase(BaseModel):
    client_id: uuid.UUID = Field(..., description="Client (tenant) ID")
    module_id: uuid.UUID = Field(..., description="Module ID being assigned")
    is_active: Optional[bool] = Field(True, description="Whether the module is active for this client")
    notes: Optional[str] = Field(None, description="Optional notes about the assignment")


class ClientModuleCreate(ClientModuleBase):
    pass


class ClientModuleUpdate(BaseModel):
    is_active: Optional[bool] = Field(None, description="Activate or deactivate the module for this client")
    notes: Optional[str] = Field(None, description="Notes about the assignment")
    updated_by: Optional[uuid.UUID] = Field(None, description="User performing the update")


class ClientModuleResponse(ClientModuleBase):
    id: uuid.UUID
    assigned_at: datetime
    assigned_by: Optional[uuid.UUID] = None
    updated_at: datetime
    updated_by: Optional[uuid.UUID] = None

    model_config = ConfigDict(from_attributes=True)


class ClientModuleListResponse(BaseModel):
    client_modules: List[ClientModuleResponse]
    total: int
    page: int
    size: int
    total_pages: int

    model_config = ConfigDict(from_attributes=True)
