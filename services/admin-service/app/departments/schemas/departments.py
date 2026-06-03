from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from datetime import datetime
from decimal import Decimal
import uuid

class DepartmentBase(BaseModel):
    department_name: str = Field(..., min_length=1, max_length=100, description="Department name")
    description: Optional[str] = Field(None, description="Department description")
    department_code: Optional[str] = Field(None, min_length=1, max_length=20, description="Department code")
    entity_id: Optional[uuid.UUID] = Field(None, description="Entity ID this department belongs to")
    parent_department_id: Optional[uuid.UUID] = Field(None, description="Parent department ID for hierarchy")
    manager_id: Optional[uuid.UUID] = Field(None, description="Manager user ID")
    department_type: Optional[str] = Field(None, max_length=50, description="Department type")
    cost_center: Optional[str] = Field(None, max_length=50, description="Department cost center")
    location: str = Field(..., max_length=255, description="Department location")
    phone: str = Field(..., max_length=20, description="Department phone number")
    email: str = Field(..., max_length=255, description="Department email address")
    annual_budget: Decimal = Field(..., description="Department annual budget")
    reporting_structure: str = Field(..., max_length=100, description="Department reporting structure")
    budget_info: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Budget information")
    department_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Department metadata")
    is_active: Optional[bool] = Field(True, description="Whether the department is active")
    client_id: uuid.UUID = Field(..., description="Client ID this department belongs to")

    @validator('email')
    def validate_email(cls, v):
        import re
        if v and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
            raise ValueError('Invalid email format')
        return v

class DepartmentCreate(DepartmentBase):
    @validator('entity_id', pre=True)
    def validate_entity_id(cls, v):
        # Convert empty string to None
        if v == '':
            return None
        return v

class DepartmentUpdate(BaseModel):
    department_name: Optional[str] = Field(None, min_length=1, max_length=100, description="Department name")
    description: Optional[str] = Field(None, description="Department description")
    department_code: Optional[str] = Field(None, max_length=20, description="Department code")
    parent_department_id: Optional[uuid.UUID] = Field(None, description="Parent department ID for hierarchy")
    manager_id: Optional[uuid.UUID] = Field(None, description="Manager user ID")
    department_type: Optional[str] = Field(None, max_length=50, description="Department type")
    cost_center: Optional[str] = Field(None, max_length=50, description="Department cost center")
    location: Optional[str] = Field(None, max_length=255, description="Department location")
    phone: Optional[str] = Field(None, max_length=20, description="Department phone number")
    email: Optional[str] = Field(None, max_length=255, description="Department email address")
    annual_budget: Optional[Decimal] = Field(None, description="Department annual budget")
    reporting_structure: Optional[str] = Field(None, max_length=100, description="Department reporting structure")
    budget_info: Optional[Dict[str, Any]] = Field(None, description="Budget information")
    department_metadata: Optional[Dict[str, Any]] = Field(None, description="Department metadata")
    is_active: Optional[bool] = Field(None, description="Whether the department is active")

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