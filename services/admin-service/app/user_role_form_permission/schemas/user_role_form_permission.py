from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime
from uuid import UUID


class FormPermissionItem(BaseModel):
    """Schema for individual form permission item - simplified based on menu selection"""
    id: str = Field(
        ...,
        description="Form UUID",
        json_schema_extra={"example": "8ef5debb-b170-4659-a8ad-a73d41e5365d"}
    )
    menu_id: str = Field(
        ...,
        description="Menu ID that this form belongs to (from userrole_permission.menu_permissions)",
        json_schema_extra={"example": "cd829d19-3ad4-4b43-93dc-855774e3afd0"}
    )
    form_access: Optional[List[str]] = Field(
        None,
        description="Form access permissions: ['read'], ['read', 'write'], or ['disable']",
        json_schema_extra={"example": ["read", "write"]}
    )

    @field_validator('form_access')
    def validate_form_access(cls, v):
        """Validate form access array contains valid values"""
        if v is None:
            return v
        valid_values = {'read', 'write', 'disable'}
        if not v:
            raise ValueError("Form access array cannot be empty if provided")
        for val in v:
            if val not in valid_values:
                raise ValueError(f"Invalid access value: {val}. Must be one of {valid_values}")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "8ef5debb-b170-4659-a8ad-a73d41e5365d",
                "menu_id": "cd829d19-3ad4-4b43-93dc-855774e3afd0",
                "form_access": ["read", "write"]
            }
        }
    )


class RoleFormPermissionBase(BaseModel):
    """Base schema for Role Form Permission"""
    form_permissions: List[FormPermissionItem] = Field(
        default=[],
        description="Array of form permissions based on selected menus from userrole_permission",
        json_schema_extra={
            "example": [
                {
                    "id": "8ef5debb-b170-4659-a8ad-a73d41e5365d",
                    "menu_id": "cd829d19-3ad4-4b43-93dc-855774e3afd0",
                    "form_access": ["write"]
                },
                {
                    "id": "b0b34143-dffb-4fcb-b08b-a8b740b70dfa",
                    "menu_id": "c3101217-3fa8-4e5e-8762-92a306c3c7d6",
                    "form_access": ["read"]
                }
            ]
        }
    )


class RoleFormPermissionCreate(RoleFormPermissionBase):
    """Schema for creating a role form permission"""
    userrole_permission_id: UUID = Field(..., description="User role permission ID (required - to get menu selections)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "userrole_permission_id": "9ab12c34-5678-90de-f123-456789abcdef",
                "form_permissions": [
                    {
                        "id": "8ef5debb-b170-4659-a8ad-a73d41e5365d",
                        "menu_id": "cd829d19-3ad4-4b43-93dc-855774e3afd0",
                        "form_access": ["write"]
                    },
                    {
                        "id": "b0b34143-dffb-4fcb-b08b-a8b740b70dfa",
                        "menu_id": "c3101217-3fa8-4e5e-8762-92a306c3c7d6",
                        "form_access": ["read"]
                    }
                ]
            }
        }
    )


class RoleFormPermissionUpdate(BaseModel):
    """Schema for updating a role form permission"""
    form_permissions: Optional[List[FormPermissionItem]] = Field(
        None,
        description="Array of form permissions based on selected menus"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "form_permissions": [
                    {
                        "id": "8ef5debb-b170-4659-a8ad-a73d41e5365d",
                        "menu_id": "cd829d19-3ad4-4b43-93dc-855774e3afd0",
                        "form_access": ["read"]
                    }
                ]
            }
        }
    )


class RoleFormPermissionResponse(BaseModel):
    """Schema for role form permission response"""
    id: UUID
    sino: int
    user_role_id: UUID
    userrole_basic_id: UUID
    userrole_permission_id: UUID
    form_permissions: List[FormPermissionItem] = Field(default_factory=list)
    form_access: Optional[str] = Field(None, description="Highest form access level: read, write, or disable")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "sino": 1,
                "user_role_id": "7fb46a5d-462f-4c7e-8430-505d4a1cd050",
                "userrole_basic_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "userrole_permission_id": "9ab12c34-5678-90de-f123-456789abcdef",
                "form_permissions": [
                    {
                        "id": "8ef5debb-b170-4659-a8ad-a73d41e5365d",
                        "menu_id": "cd829d19-3ad4-4b43-93dc-855774e3afd0",
                        "form_access": ["write"]
                    }
                ],
                "form_access": "write",
                "created_at": "2026-01-21T05:44:23.234Z",
                "updated_at": "2026-01-21T05:44:23.234Z"
            }
        }
    )


class RoleFormPermissionListResponse(BaseModel):
    """Schema for paginated role form permission list response"""
    items: List[RoleFormPermissionResponse]
    total: int
    page: int
    size: int
    total_pages: int

    model_config = ConfigDict(from_attributes=True)
