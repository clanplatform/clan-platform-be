from typing import Optional
from pydantic import BaseModel, Field, validator
from datetime import datetime
import uuid


class UserGroupBase(BaseModel):
    """Base schema for UserGroup.

    tenant_id is intentionally omitted: it is derived from the JWT server-side,
    never sent in the request or returned in the response.
    is_active is intentionally omitted: it is a backend-operational column
    (defaulted True on create, toggled by delete), never in the schema.
    """
    group_name: str = Field(..., min_length=1, max_length=100, description="Group name")
    group_code: Optional[str] = Field(None, max_length=50, description="Group code")
    default_role_id: Optional[uuid.UUID] = Field(None, description="Default role assigned to users in this group (user_role.id)")
    description: Optional[str] = Field(None, description="Purpose of this group")

    @validator('default_role_id', pre=True)
    def empty_str_to_none(cls, v):
        # Convert empty string to None
        if v == '':
            return None
        return v


class UserGroupCreate(UserGroupBase):
    """Schema for creating a new user group"""
    pass


class UserGroupUpdate(BaseModel):
    """Schema for updating an existing user group"""
    group_name: Optional[str] = Field(None, min_length=1, max_length=100, description="Group name")
    group_code: Optional[str] = Field(None, max_length=50, description="Group code")
    default_role_id: Optional[uuid.UUID] = Field(None, description="Default role assigned to users in this group (user_role.id)")
    description: Optional[str] = Field(None, description="Purpose of this group")

    @validator('default_role_id', pre=True)
    def empty_str_to_none(cls, v):
        if v == '':
            return None
        return v


class UserGroupResponse(UserGroupBase):
    """Schema for user group response"""
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
