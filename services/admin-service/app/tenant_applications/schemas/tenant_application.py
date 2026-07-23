from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
import uuid


class TenantApplicationBase(BaseModel):
    tenant_id: uuid.UUID = Field(..., description="Tenant ID")
    application_id: uuid.UUID = Field(..., description="Application ID being assigned")
    is_active: Optional[bool] = Field(True, description="Whether the application license is active for this tenant")
    notes: Optional[str] = Field(None, description="Optional notes about the assignment")


class TenantApplicationCreate(TenantApplicationBase):
    pass


class TenantApplicationUpdate(BaseModel):
    is_active: Optional[bool] = Field(None, description="Activate or deactivate the application for this tenant")
    notes: Optional[str] = Field(None, description="Notes about the assignment")
    updated_by: Optional[uuid.UUID] = Field(None, description="User performing the update")


class TenantApplicationResponse(TenantApplicationBase):
    id: uuid.UUID
    assigned_at: datetime
    assigned_by: Optional[uuid.UUID] = None
    updated_at: datetime
    updated_by: Optional[uuid.UUID] = None

    model_config = ConfigDict(from_attributes=True)


class TenantApplicationListResponse(BaseModel):
    tenant_applications: List[TenantApplicationResponse]
    total: int
    page: int
    size: int
    total_pages: int

    model_config = ConfigDict(from_attributes=True)
