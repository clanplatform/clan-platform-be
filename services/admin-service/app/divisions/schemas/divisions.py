from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from datetime import datetime
import uuid

# Nested schemas for relationships
class ClientNested(BaseModel):
    client_id: uuid.UUID
    client_name: str
    
    class Config:
        from_attributes = True

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

class DivisionNested(BaseModel):
    id: uuid.UUID
    division_name: str
    division_code: str
    
    class Config:
        from_attributes = True

class DivisionBase(BaseModel):
    division_name: str = Field(..., min_length=1, max_length=100, description="Division name")
    division_code: str = Field(..., min_length=1, max_length=20, description="Division code")
    description: Optional[str] = Field(None, description="Division description")
    client_id: uuid.UUID = Field(..., description="Client ID this division belongs to")
    entity_id: Optional[uuid.UUID] = Field(None, description="Entity ID this division belongs to")
    department_id: Optional[uuid.UUID] = Field(None, description="Department ID this division belongs to")
    parent_division_id: Optional[uuid.UUID] = Field(None, description="Parent division ID")
    hierarchy_level: Optional[str] = Field("1", max_length=10, description="Hierarchy level")
    division_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Division metadata")
    is_active: Optional[bool] = Field(True, description="Whether the division is active")

    @validator('entity_id', pre=True)
    def validate_entity_id(cls, v):
        # Convert empty string to None
        if v == '':
            return None
        return v

    @validator('department_id', pre=True)
    def validate_department_id(cls, v):
        # Convert empty string to None
        if v == '':
            return None
        return v

    @validator('parent_division_id', pre=True)
    def validate_parent_division_id(cls, v):
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
    client_id: Optional[uuid.UUID] = Field(None, description="Client ID this division belongs to")
    entity_id: Optional[uuid.UUID] = Field(None, description="Entity ID this division belongs to")
    department_id: Optional[uuid.UUID] = Field(None, description="Department ID this division belongs to")
    parent_division_id: Optional[uuid.UUID] = Field(None, description="Parent division ID")
    hierarchy_level: Optional[str] = Field(None, max_length=10, description="Hierarchy level")
    division_metadata: Optional[Dict[str, Any]] = Field(None, description="Division metadata")
    is_active: Optional[bool] = Field(None, description="Whether the division is active")

    @validator('entity_id', pre=True)
    def validate_entity_id(cls, v):
        if v == '':
            return None
        return v

    @validator('department_id', pre=True)
    def validate_department_id(cls, v):
        if v == '':
            return None
        return v

    @validator('parent_division_id', pre=True)
    def validate_parent_division_id(cls, v):
        if v == '':
            return None
        return v

class DivisionResponse(DivisionBase):
    """Schema for division response with all fields"""
    id: uuid.UUID
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    # Nested relationships (optional)
    client: Optional[ClientNested] = None
    entity: Optional[EntityNested] = None
    department: Optional[DepartmentNested] = None
    parent_division: Optional[DivisionNested] = None
    
    class Config:
        from_attributes = True
