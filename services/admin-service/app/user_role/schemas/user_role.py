from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from datetime import datetime
from uuid import UUID


# ============================================================================
# UserRoleBasic Schemas
# ============================================================================

# What the role's permissions apply against: whole tenant, the user's own
# assigned entities/branches (usersetup_basic.entity_id, already an array —
# so a role scoped to "branch_entity" naturally covers all of a user's
# assigned entities), department, or division.
ACCESS_SCOPE_VALUES = {"whole_organization", "branch_entity", "department", "division"}


def _validate_access_scope(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    if v not in ACCESS_SCOPE_VALUES:
        raise ValueError(f"Invalid access_scope: {v}. Must be one of {sorted(ACCESS_SCOPE_VALUES)}")
    return v


class UserRoleBasicBase(BaseModel):
    """Base schema for UserRoleBasic.

    tenant_id is intentionally omitted: it is derived from the JWT server-side,
    never sent in the request or returned in the response (consistent with the
    other admin-service modules).
    """
    role_name: str = Field(..., min_length=1, max_length=100, description="Role name")
    role_code: str = Field(..., min_length=1, max_length=50, description="Role code (unique identifier)")
    description: Optional[str] = Field(None, description="Role description")
    role_level: int = Field(default=1, ge=1, description="Role hierarchy level")
    access_scope: Optional[str] = Field(
        None, max_length=50,
        description="Access scope: whole_organization, branch_entity, department, or division",
    )
    is_admin: bool = Field(default=False, description="Whether this is an admin role")
    default_for_new_users: bool = Field(default=False, description="Default role for new users")
    active: bool = Field(default=True, description="Whether the role is active")

    @field_validator("access_scope")
    @classmethod
    def validate_access_scope(cls, v):
        return _validate_access_scope(v)


class UserRoleBasicCreate(UserRoleBasicBase):
    """Schema for creating a new user role"""
    parent_role: Optional[str] = Field(
        None, max_length=50,
        description="Parent role's role_code (Reports to) — must match an existing "
                    "role's role_code for this tenant; resolved server-side to "
                    "userrole_basic.parent_role_id.",
    )


class UserRoleBasicUpdate(BaseModel):
    """Schema for updating a user role.

    tenant_id is intentionally omitted (JWT-derived, immutable after creation).
    """
    role_name: Optional[str] = Field(None, min_length=1, max_length=100, description="Role name")
    role_code: Optional[str] = Field(None, min_length=1, max_length=50, description="Role code")
    description: Optional[str] = Field(None, description="Role description")
    role_level: Optional[int] = Field(None, ge=1, description="Role hierarchy level")
    parent_role: Optional[str] = Field(
        None, max_length=50,
        description="Parent role's role_code (Reports to) — must match an existing "
                    "role's role_code for this tenant; resolved server-side to "
                    "userrole_basic.parent_role_id.",
    )
    access_scope: Optional[str] = Field(
        None, max_length=50,
        description="Access scope: whole_organization, branch_entity, department, or division",
    )
    is_admin: Optional[bool] = Field(None, description="Whether this is an admin role")
    default_for_new_users: Optional[bool] = Field(None, description="Default role for new users")
    active: Optional[bool] = Field(None, description="Whether the role is active")

    @field_validator("access_scope")
    @classmethod
    def validate_access_scope(cls, v):
        return _validate_access_scope(v)


class UserRoleBasicResponse(UserRoleBasicBase):
    """Schema for user role response"""
    id: UUID
    parent_role_id: Optional[UUID] = Field(None, description="Parent role id (user_role.id) — Reports to")
    parent_role: Optional[str] = Field(None, description="Parent role's role_code (Reports to), resolved from parent_role_id for display")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# UserRolePermission Schemas
# ============================================================================

class PermissionItem(BaseModel):
    """Schema for permission item with multiple IDs sharing the same access level"""
    id: str = Field(
        ...,
        description="UUID for menu/form",
        json_schema_extra={"example": "78a97558-6e3d-4514-9fa0-dc7fdece5665"}
    )
    application_id: Optional[str] = Field(
        None,
        description="Application ID from applications table",
        json_schema_extra={"example": "app-uuid-123"}
    )
    modules_id: Optional[str] = Field(
        None,
        description="Module ID from modules table",
        json_schema_extra={"example": "module-uuid-456"}
    )
    menu_access: Optional[List[str]] = Field(
        None,
        description="Menu access permissions: ['read'], ['read', 'write'], or ['disable']",
        json_schema_extra={"example": ["read", "write"]}
    )
    form_access: Optional[List[str]] = Field(
        None,
        description="Form access permissions: ['read'], ['read', 'write'], or ['disable']",
        json_schema_extra={"example": ["write"]}
    )
    button_access: Optional[List[str]] = Field(
        None,
        description="Button access permissions: ['read'], ['read', 'write'], or ['disable']",
        json_schema_extra={"example": ["write"]}
    )


    @model_validator(mode="before")
    @classmethod
    def _map_stored_access_key(cls, data):
        """The JSONB actually persisted on userrole_permission.menu_permissions/
        button_permissions/form_permissions stores the access level under a
        generic "access" key (see UserRoleService.build_permission_row /
        _build_button_perms / _build_form_perms) — not menu_access/
        form_access/button_access, which is what this schema (used for both
        the direct Roles API and onboarding) actually exposes. Without this,
        every permission read back from the DB shows menu_access/form_access/
        button_access as null regardless of what was granted."""
        if isinstance(data, dict) and "access" in data:
            access = data["access"]
            data.setdefault("menu_access", access)
            data.setdefault("form_access", access)
            data.setdefault("button_access", access)
        return data

    @field_validator('menu_access', 'form_access', 'button_access')
    def validate_access(cls, v):
        """Validate access array contains valid values"""
        if v is None:
            return v
        valid_values = {'read', 'write', 'disable'}
        if not v:
            raise ValueError("Access array cannot be empty if provided")
        for val in v:
            if val not in valid_values:
                raise ValueError(f"Invalid access value: {val}. Must be one of {valid_values}")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "78a97558-6e3d-4514-9fa0-dc7fdece5665",
                "application_id": "app-uuid-123",
                "modules_id": "module-uuid-456",
                "menu_access": ["read", "write"]
            }
        }
    )


class UserRolePermissionBase(BaseModel):
    """Base schema for UserRolePermission - supports individual access per entity"""
    menu_permissions: Optional[List[PermissionItem]] = Field(
        default=[],
        description="Array of menu permissions - each menu has individual access",
        json_schema_extra={
            "example": [
                {
                    "id": "cd829d19-3ad4-4b43-93dc-855774e3afd0",
                    "application_id": "app-uuid-123",
                    "modules_id": "module-uuid-456",
                    "menu_access": ["write"]
                },
                {
                    "id": "c3101217-3fa8-4e5e-8762-92a306c3c7d6",
                    "application_id": "app-uuid-789",
                    "modules_id": "module-uuid-012",
                    "menu_access": ["read"]
                }
            ]
        }
    )
    button_permissions: Optional[List[PermissionItem]] = Field(
        default=[],
        description="Array of button permissions - each button has individual access",
        json_schema_extra={
            "example": [
                {
                    "id": "9a1c2f7e-1111-4bbb-9ccc-2b6d5e4f7a01",
                    "button_access": ["write"]
                }
            ]
        }
    )
    form_permissions: Optional[List[PermissionItem]] = Field(
        default=[],
        description="Array of form permissions - each form has individual access",
        json_schema_extra={
            "example": [
                {
                    "id": "8ef5debb-b170-4659-a8ad-a73d41e5365d",
                    "application_id": "app-uuid-123",
                    "modules_id": "module-uuid-456",
                    "form_access": ["write"]
                }
            ]
        }
    )



class UserRolePermissionCreate(UserRolePermissionBase):
    """Schema for creating a new user role permission with multiple IDs"""
    user_role_id: Optional[UUID] = Field(None, description="User role ID (optional - will be auto-fetched from userrole_basic if not provided)")
    userrole_basic_id: UUID = Field(..., description="User role basic ID this permission belongs to")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "userrole_basic_id": "7fb46a5d-462f-4c7e-8430-505d4a1cd050",
                "menu_permissions": [
                    {
                        "id": "cd829d19-3ad4-4b43-93dc-855774e3afd0",
                        "application_id": "app-uuid-123",
                        "modules_id": "module-uuid-456",
                        "menu_access": ["write"]
                    },
                    {
                        "id": "c3101217-3fa8-4e5e-8762-92a306c3c7d6",
                        "application_id": "app-uuid-789",
                        "modules_id": "module-uuid-012",
                        "menu_access": ["write"]
                    },
                    {
                        "id": "a21b430f-c9e1-4ccc-abba-7002f1cb176a",
                        "application_id": "app-uuid-123",
                        "modules_id": "module-uuid-456",
                        "menu_access": ["read"]
                    },
                    {
                        "id": "593fe78f-ba99-48cc-8d19-799f41995ab4",
                        "application_id": "app-uuid-789",
                        "modules_id": "module-uuid-012",
                        "menu_access": ["write"]
                    }
                ]
            }
        }
    )


class UserRolePermissionUpdate(BaseModel):
    """Schema for updating a user role permission - supports individual access per entity"""
    userrole_basic_id: Optional[UUID] = Field(None, description="User role basic ID this permission belongs to")
    menu_permissions: Optional[List[PermissionItem]] = Field(
        None,
        description="Array of menu permissions - each menu has individual access",
        json_schema_extra={
            "example": [
                {
                    "id": "cd829d19-3ad4-4b43-93dc-855774e3afd0",
                    "application_id": "app-uuid-123",
                    "modules_id": "module-uuid-456",
                    "menu_access": ["write"]
                },
                {
                    "id": "c3101217-3fa8-4e5e-8762-92a306c3c7d6",
                    "application_id": "app-uuid-789",
                    "modules_id": "module-uuid-012",
                    "menu_access": ["read"]
                }
            ]
        }
    )
    button_permissions: Optional[List[PermissionItem]] = Field(
        None,
        description="Array of button permissions - each button has individual access",
        json_schema_extra={
            "example": [
                {
                    "id": "9a1c2f7e-1111-4bbb-9ccc-2b6d5e4f7a01",
                    "button_access": ["read"]
                }
            ]
        }
    )
    form_permissions: Optional[List[PermissionItem]] = Field(
        None,
        description="Array of form permissions - each form has individual access",
        json_schema_extra={
            "example": [
                {
                    "id": "8ef5debb-b170-4659-a8ad-a73d41e5365d",
                    "application_id": "app-uuid-123",
                    "modules_id": "module-uuid-456",
                    "form_access": ["read"]
                }
            ]
        }
    )



class UserRolePermissionResponse(BaseModel):
    """Schema for user role permission response with individual access per item"""
    id: UUID
    user_role_id: UUID
    userrole_basic_id: UUID
    menu_permissions: List[PermissionItem] = Field(default_factory=list)
    menu_access: Optional[str] = Field(None, description="Highest menu access level: read, write, or disable")
    button_permissions: List[PermissionItem] = Field(default_factory=list)
    button_access: Optional[str] = Field(None, description="Highest button access level: read, write, or disable")
    form_permissions: List[PermissionItem] = Field(default_factory=list)
    form_access: Optional[str] = Field(None, description="Highest form access level: read, write, or disable")

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "user_role_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "userrole_basic_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "menu_permissions": [
                    {
                        "id": "cd829d19-3ad4-4b43-93dc-855774e3afd0",
                        "application_id": "app-uuid-123",
                        "modules_id": "module-uuid-456",
                        "menu_access": ["write"]
                    },
                    {
                        "id": "c3101217-3fa8-4e5e-8762-92a306c3c7d6",
                        "application_id": "app-uuid-789",
                        "modules_id": "module-uuid-012",
                        "menu_access": ["read"]
                    }
                ],
                "menu_access": "write",
                "created_at": "2026-01-21T05:44:23.234Z",
                "updated_at": "2026-01-21T05:44:23.234Z"
            }
        }
    )


# ============================================================================
# Combined/Nested Schemas
# ============================================================================

class UserRoleWithDetails(UserRoleBasicResponse):
    """Schema for user role with all related permissions"""
    permissions: List[UserRolePermissionResponse] = Field(default_factory=list, description="Role permissions")

    model_config = ConfigDict(from_attributes=True)


class UserRoleCreateWithDetails(BaseModel):
    """Schema for creating a user role with permissions in one request"""
    basic: UserRoleBasicCreate
    permissions: Optional[List[UserRolePermissionBase]] = Field(default_factory=list, description="Initial permissions")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "basic": {
                    "role_name": "Manager",
                    "role_code": "MGR",
                    "description": "Manager role",
                    "role_level": 2,
                    "parent_role": "DIR",
                    "access_scope": "whole_organization",
                    "is_admin": False,
                    "default_for_new_users": False,
                    "active": True
                },
                "permissions": [
                    {
                        "menu_permissions": [
                            {
                                "id": "cd829d19-3ad4-4b43-93dc-855774e3afd0",
                                "application_id": "app-uuid-123",
                                "modules_id": "module-uuid-456",
                                "menu_access": ["write"]
                            },
                            {
                                "id": "c3101217-3fa8-4e5e-8762-92a306c3c7d6",
                                "application_id": "app-uuid-789",
                                "modules_id": "module-uuid-012",
                                "menu_access": ["read"]
                            }
                        ],
                        "form_permissions": [
                            {
                                "id": "8ef5debb-b170-4659-a8ad-a73d41e5365d",
                                "application_id": "app-uuid-123",
                                "modules_id": "module-uuid-456",
                                "form_access": ["write"]
                            }
                        ],
                        "button_permissions": [
                            {
                                "id": "9a1c2f7e-1111-4bbb-9ccc-2b6d5e4f7a01",
                                "button_access": ["read"]
                            }
                        ]
                    }
                ]
            }
        }
    )


class UserRoleUpdateWithDetails(BaseModel):
    """Schema for updating a user role with permissions in one request"""
    basic: Optional[UserRoleBasicUpdate] = Field(None, description="Basic role information to update")
    permissions: Optional[List[UserRolePermissionBase]] = Field(None, description="Permissions to replace (replaces all existing)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "basic": {
                    "role_name": "Updated Admin Role",
                    "description": "Updated description",
                    "active": True
                },
                "permissions": [
                    {
                        "menu_permissions": [
                            {"id": "menu-uuid-1", "menu_access": ["write"]},
                            {"id": "menu-uuid-2", "menu_access": ["read"]}
                        ],
                        "form_permissions": [
                            {"id": "form-uuid-1", "form_access": ["write"]}
                        ]
                    }
                ]
            }
        }
    )


# ============================================================================
# Entity Reference Schemas (for fetching from menus/forms)
# ============================================================================

class EntityReference(BaseModel):
    """Schema for entity reference (menu/form)"""
    entity_type: str = Field(..., description="Entity type: 'menu', 'form'")
    entity_id: UUID = Field(..., description="Entity ID")
    name: str = Field(..., description="Entity name")
    access: List[str] = Field(..., description="Access permissions from the entity")

    model_config = ConfigDict(from_attributes=True)


class AvailableEntitiesResponse(BaseModel):
    """Schema for listing available entities that can be assigned to roles"""
    menus: List[EntityReference] = Field(default_factory=list, description="Available menus")
    forms: List[EntityReference] = Field(default_factory=list, description="Available forms")


# ============================================================================
# User Form Permission Schemas (Separate from Role Permissions)
# ============================================================================

class UserFormPermissionBase(BaseModel):
    """Base schema for User Form Permission"""
    form_permissions: Optional[List[PermissionItem]] = Field(
        default=[],
        description="Array of form permissions - each form has individual access",
        json_schema_extra={
            "example": [
                {
                    "id": "8ef5debb-b170-4659-a8ad-a73d41e5365d",
                    "application_id": "app-uuid-123",
                    "modules_id": "module-uuid-456",
                    "form_access": ["write"]
                },
                {
                    "id": "b0b34143-dffb-4fcb-b08b-a8b740b70dfa",
                    "application_id": "app-uuid-789",
                    "modules_id": "module-uuid-012",
                    "form_access": ["write"]
                }
            ]
        }
    )


class UserFormPermissionCreate(UserFormPermissionBase):
    """Schema for creating user form permissions by role_id"""
    pass


class UserFormPermissionUpdate(BaseModel):
    """Schema for updating user form permissions"""
    form_permissions: Optional[List[PermissionItem]] = Field(
        None,
        description="Array of form permissions - each form has individual access",
        json_schema_extra={
            "example": [
                {
                    "id": "8ef5debb-b170-4659-a8ad-a73d41e5365d",
                    "application_id": "app-uuid-123",
                    "modules_id": "module-uuid-456",
                    "form_access": ["write"]
                },
                {
                    "id": "b0b34143-dffb-4fcb-b08b-a8b740b70dfa",
                    "application_id": "app-uuid-789",
                    "modules_id": "module-uuid-012",
                    "form_access": ["read"]
                }
            ]
        }
    )


class UserFormPermissionResponse(BaseModel):
    """Schema for user form permission response"""
    id: UUID
    user_role_id: UUID
    userrole_basic_id: UUID
    form_permissions: List[PermissionItem] = Field(default_factory=list)
    form_access: Optional[str] = Field(None, description="Highest form access level: read, write, or disable")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "user_role_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "userrole_basic_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "form_permissions": [
                    {
                        "id": "8ef5debb-b170-4659-a8ad-a73d41e5365d",
                        "application_id": "app-uuid-123",
                        "modules_id": "module-uuid-456",
                        "form_access": ["write"]
                    }
                ],
                "form_access": "write",
                "created_at": "2026-01-21T05:44:23.234Z",
                "updated_at": "2026-01-21T05:44:23.234Z"
            }
        }
    )
   

