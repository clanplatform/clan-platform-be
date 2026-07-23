from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
import uuid


class TenantModuleBase(BaseModel):
    tenant_id: uuid.UUID = Field(..., description="Tenant ID")
    module_id: uuid.UUID = Field(..., description="Module ID being assigned")
    is_active: Optional[bool] = Field(True, description="Whether the module is active for this tenant")
    notes: Optional[str] = Field(None, description="Optional notes about the assignment")


class TenantModuleCreate(TenantModuleBase):
    pass


class TenantModuleUpdate(BaseModel):
    is_active: Optional[bool] = Field(None, description="Activate or deactivate the module for this tenant")
    notes: Optional[str] = Field(None, description="Notes about the assignment")
    updated_by: Optional[uuid.UUID] = Field(None, description="User performing the update")


class TenantModuleResponse(TenantModuleBase):
    id: uuid.UUID
    assigned_at: datetime
    assigned_by: Optional[uuid.UUID] = None
    updated_at: datetime
    updated_by: Optional[uuid.UUID] = None

    model_config = ConfigDict(from_attributes=True)


class TenantModuleListResponse(BaseModel):
    tenant_modules: List[TenantModuleResponse]
    total: int
    page: int
    size: int
    total_pages: int

    model_config = ConfigDict(from_attributes=True)
