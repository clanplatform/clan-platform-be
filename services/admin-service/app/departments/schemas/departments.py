from typing import Optional
from pydantic import BaseModel, Field, validator
from datetime import datetime
from decimal import Decimal
import uuid

class DepartmentBase(BaseModel):
    department_name: str = Field(..., min_length=1, max_length=100, description="Department name")
    department_code: Optional[str] = Field(None, min_length=1, max_length=20, description="Department code")
    entity_id: uuid.UUID = Field(..., description="Entity ID this department belongs to")
    department_type: Optional[str] = Field(None, max_length=50, description="Department type")
    cost_center: Optional[str] = Field(None, max_length=50, description="Department cost center")
    department_head: Optional[str] = Field(None, max_length=100, description="Department head / manager")
    location: str = Field(..., max_length=255, description="Department location")
    phone: str = Field(..., max_length=20, description="Department phone number")
    email: str = Field(..., max_length=255, description="Department email address")
    annual_budget: Decimal = Field(..., description="Department annual budget")
    reporting_structure: Optional[str] = Field(None, max_length=100, description="Department reporting structure")
    # is_active is intentionally omitted from the schema: it is a backend-operational
    # column (defaulted True on create, toggled by delete/restore), never sent in the
    # request or returned in the response.
    # tenant_id is intentionally omitted: it is derived from the JWT server-side,
    # never sent in the request or returned in the response.

    @validator('email')
    def validate_email(cls, v):
        import re
        if v and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
            raise ValueError('Invalid email format')
        return v

class DepartmentCreate(DepartmentBase):
    pass

class DepartmentUpdate(BaseModel):
    department_name: Optional[str] = Field(None, min_length=1, max_length=100, description="Department name")
    department_code: Optional[str] = Field(None, max_length=20, description="Department code")
    department_type: Optional[str] = Field(None, max_length=50, description="Department type")
    cost_center: Optional[str] = Field(None, max_length=50, description="Department cost center")
    department_head: Optional[str] = Field(None, max_length=100, description="Department head / manager")
    location: Optional[str] = Field(None, max_length=255, description="Department location")
    phone: Optional[str] = Field(None, max_length=20, description="Department phone number")
    email: Optional[str] = Field(None, max_length=255, description="Department email address")
    annual_budget: Optional[Decimal] = Field(None, description="Department annual budget")
    reporting_structure: Optional[str] = Field(None, max_length=100, description="Department reporting structure")
    # is_active omitted — backend-operational only (see DepartmentBase).

    @validator('email')
    def validate_email(cls, v):
        if v is not None:
            import re
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
                raise ValueError('Invalid email format')
        return v

class DepartmentResponse(DepartmentBase):
    department_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True