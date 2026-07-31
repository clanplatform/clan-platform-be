from typing import Optional
from pydantic import BaseModel, Field, validator
from datetime import datetime
import uuid

# Nested schemas for relationships
class EntityNested(BaseModel):
    entity_id: uuid.UUID
    entity_name: str

    class Config:
        from_attributes = True

class DepartmentNested(BaseModel):
    department_id: uuid.UUID
    department_name: str
    
    class Config:
        from_attributes = True

class DivisionBase(BaseModel):
    division_name: str = Field(..., min_length=1, max_length=100, description="Division name")
    division_code: str = Field(..., min_length=1, max_length=20, description="Division code")
    description: Optional[str] = Field(None, description="Division description")
    # tenant_id is intentionally omitted: it is derived from the JWT server-side,
    # never sent in the request or returned in the response.
    # is_active is intentionally omitted: it is a backend-operational column
    # (defaulted True on create, toggled by delete/restore), never in the schema.
    entity_id: uuid.UUID = Field(..., description="Entity ID this division belongs to")
    department_id: Optional[uuid.UUID] = Field(None, description="Department ID this division belongs to")
    division_head: Optional[str] = Field(None, max_length=100, description="Division head / lead")
    hierarchy_level: Optional[str] = Field("1", max_length=10, description="Hierarchy level")

    @validator('department_id', pre=True)
    def validate_department_id(cls, v):
        # Convert empty string to None
        if v == '':
            return None
        return v

class DivisionCreate(DivisionBase):
    """Schema for creating a new division"""
    pass

class DivisionUpdate(BaseModel):
    """Schema for updating an existing division"""
    division_name: Optional[str] = Field(None, min_length=1, max_length=100, description="Division name")
    division_code: Optional[str] = Field(None, min_length=1, max_length=20, description="Division code")
    description: Optional[str] = Field(None, description="Division description")
    # tenant_id is intentionally omitted: it is derived from the JWT and immutable.
    entity_id: Optional[uuid.UUID] = Field(None, description="Entity ID this division belongs to (cannot be changed after creation)")
    department_id: Optional[uuid.UUID] = Field(None, description="Department ID this division belongs to")
    division_head: Optional[str] = Field(None, max_length=100, description="Division head / lead")
    hierarchy_level: Optional[str] = Field(None, max_length=10, description="Hierarchy level")

    @validator('department_id', pre=True)
    def validate_department_id(cls, v):
        if v == '':
            return None
        return v

class DivisionResponse(DivisionBase):
    """Schema for division response with all fields"""
    id: uuid.UUID
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    # Nested relationships (optional). tenant is intentionally not exposed —
    # tenant identity stays in the JWT, out of the division JSON.
    entity: Optional[EntityNested] = None
    department: Optional[DepartmentNested] = None

    class Config:
        from_attributes = True
