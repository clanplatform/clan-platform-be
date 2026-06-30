from pydantic import BaseModel, EmailStr, Field, field_validator, SecretStr
from typing import Optional, List
from uuid import UUID
from datetime import date, datetime


# ============================================================================
# UserSetupBasic Schemas
# ============================================================================

class UserSetupBasicBase(BaseModel):
    """Base schema for UserSetupBasic"""
    firstname: str = Field(..., min_length=1, max_length=100, description="First name")
    lastname: str = Field(..., min_length=1, max_length=100, description="Last name")
    employee_id: str = Field(..., min_length=1, max_length=50, description="Employee ID (unique)")
    username: str = Field(..., min_length=1, max_length=100, description="Username (unique)")
    email: EmailStr = Field(..., description="Email address (unique)")
    phone_number: Optional[str] = Field(None, max_length=20, description="Phone number")
    status: str = Field(default='active', max_length=50, description="Employment status")
    start_date: Optional[date] = Field(None, description="Employment start date")
    end_date: Optional[date] = Field(None, description="Employment end date")
    tem_employee: bool = Field(default=False, description="Temporary employee flag")
    department: Optional[UUID] = Field(None, description="Department ID")
    division: Optional[UUID] = Field(None, description="Division ID")
    job_code: Optional[UUID] = Field(None, description="Job code ID")
    manage_roles: Optional[List[UUID]] = Field(None, description="Array of role IDs user can manage")
    default_dept: Optional[UUID] = Field(None, description="Default department ID")
    reporting_to: Optional[UUID] = Field(None, description="Manager's user ID")
    entities: Optional[List[UUID]] = Field(None, description="Array of entity IDs")
    default_entity: Optional[UUID] = Field(None, description="Default entity ID")
    tenant_id: Optional[UUID] = Field(None, description="Tenant ID (foreign key to tenants table)")
    view: Optional[str] = Field(None, max_length=50, description="View preference")
    dashboard_view: Optional[str] = Field(None, max_length=50, description="Dashboard view preference")


class UserSetupBasicCreate(UserSetupBasicBase):
    """Schema for creating a new user setup"""
    password: str = Field(..., min_length=8, max_length=100, description="User password (will be hashed)")

    @field_validator('reporting_to', 'department', 'division', 'job_code', 'default_dept', 'default_entity', 'tenant_id', mode='before')
    @classmethod
    def empty_str_to_none(cls, v):
        """Convert empty strings to None for UUID fields"""
        if v == '' or v == 'string':
            return None
        return v

    @field_validator('manage_roles', 'entities', mode='before')
    @classmethod
    def empty_list_to_none(cls, v):
        """Convert empty lists or lists with empty strings to None"""
        if v == [] or v == [''] or v == ['string']:
            return None
        return v


class UserSetupBasicUpdate(BaseModel):
    """Schema for updating user setup (all fields optional)"""
    firstname: Optional[str] = Field(None, min_length=1, max_length=100)
    lastname: Optional[str] = Field(None, min_length=1, max_length=100)
    employee_id: Optional[str] = Field(None, min_length=1, max_length=50)
    username: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = Field(None, max_length=20)
    password: Optional[str] = Field(None, min_length=8, max_length=100, description="New password (will be hashed)")
    status: Optional[str] = Field(None, max_length=50)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    tem_employee: Optional[bool] = None
    department: Optional[UUID] = None
    division: Optional[UUID] = None
    job_code: Optional[UUID] = None
    manage_roles: Optional[List[UUID]] = None
    default_dept: Optional[UUID] = None
    reporting_to: Optional[UUID] = None
    entities: Optional[List[UUID]] = None
    default_entity: Optional[UUID] = None
    tenant_id: Optional[UUID] = None
    view: Optional[str] = Field(None, max_length=50)
    dashboard_view: Optional[str] = Field(None, max_length=50)

    @field_validator('reporting_to', 'department', 'division', 'job_code', 'default_dept', 'default_entity', 'tenant_id', mode='before')
    @classmethod
    def empty_str_to_none(cls, v):
        """Convert empty strings to None for UUID fields"""
        if v == '' or v == 'string':
            return None
        return v

    @field_validator('manage_roles', 'entities', mode='before')
    @classmethod
    def empty_list_to_none(cls, v):
        """Convert empty lists or lists with empty strings to None"""
        if v == [] or v == [''] or v == ['string']:
            return None
        return v


class UserSetupBasicResponse(UserSetupBasicBase):
    """Schema for user setup response"""
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# UserSetupRolesEntity Schemas
# ============================================================================

class UserSetupRolesEntityBase(BaseModel):
    """Base schema for UserSetupRolesEntity"""
    assigned_roles: Optional[List[UUID]] = Field(None, description="Array of assigned role IDs")
    assigned_entities: Optional[List[UUID]] = Field(None, description="Array of assigned entity IDs")
    assigned_tenant_id: Optional[UUID] = Field(None, description="Assigned tenant ID (foreign key to tenants table)")

class UserSetupRolesEntityCreate(UserSetupRolesEntityBase):
    """Schema for creating roles and entities assignment"""
    user_setup_id: UUID = Field(..., description="User setup ID")
    usersetup_basic_id: UUID = Field(..., description="User setup basic ID")


class UserSetupRolesEntityUpdate(BaseModel):
    """Schema for updating roles and entities assignment"""
    usersetup_basic_id: Optional[UUID] = None
    assigned_roles: Optional[List[UUID]] = None
    assigned_entities: Optional[List[UUID]] = None
    assigned_tenant_id: Optional[UUID] = None


class UserSetupRolesEntityResponse(UserSetupRolesEntityBase):
    """Schema for roles and entities response"""
    id: UUID
    user_setup_id: UUID
    usersetup_basic_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# UserSetupPreference Schemas
# ============================================================================

class UserSetupPreferenceBase(BaseModel):
    """Base schema for UserSetupPreference"""
    language: str = Field(default='en', max_length=10, description="Language preference")
    timezone: str = Field(default='UTC', max_length=50, description="Timezone preference")
    theme: str = Field(default='light', max_length=20, description="Theme preference")

    @field_validator('language')
    @classmethod
    def validate_language(cls, v):
        """Validate language code"""
        valid_languages = ['en', 'es', 'fr', 'de', 'it', 'pt', 'zh', 'ja', 'ko', 'ar', 'hi']
        if v not in valid_languages:
            raise ValueError(f"Language must be one of: {', '.join(valid_languages)}")
        return v

    @field_validator('theme')
    @classmethod
    def validate_theme(cls, v):
        """Validate theme"""
        valid_themes = ['light', 'dark', 'auto']
        if v not in valid_themes:
            raise ValueError(f"Theme must be one of: {', '.join(valid_themes)}")
        return v


class UserSetupPreferenceCreate(UserSetupPreferenceBase):
    """Schema for creating user preferences"""
    user_setup_id: UUID = Field(..., description="User setup ID")
    usersetup_roles_entity_id: UUID = Field(..., description="User setup roles entity ID")
    usersetup_basic_id: UUID = Field(..., description="User setup basic ID")


class UserSetupPreferenceUpdate(BaseModel):
    """Schema for updating user preferences"""
    usersetup_roles_entity_id: Optional[UUID] = None
    usersetup_basic_id: Optional[UUID] = None
    language: Optional[str] = Field(None, max_length=10)
    timezone: Optional[str] = Field(None, max_length=50)
    theme: Optional[str] = Field(None, max_length=20)

    @field_validator('language')
    @classmethod
    def validate_language(cls, v):
        """Validate language code"""
        if v is not None:
            valid_languages = ['en', 'es', 'fr', 'de', 'it', 'pt', 'zh', 'ja', 'ko', 'ar', 'hi']
            if v not in valid_languages:
                raise ValueError(f"Language must be one of: {', '.join(valid_languages)}")
        return v

    @field_validator('theme')
    @classmethod
    def validate_theme(cls, v):
        """Validate theme"""
        if v is not None:
            valid_themes = ['light', 'dark', 'auto']
            if v not in valid_themes:
                raise ValueError(f"Theme must be one of: {', '.join(valid_themes)}")
        return v


class UserSetupPreferenceResponse(UserSetupPreferenceBase):
    """Schema for user preferences response"""
    id: UUID
    user_setup_id: UUID
    usersetup_roles_entity_id: UUID
    usersetup_basic_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Combined Schemas
# ============================================================================

class UserSetupWithDetails(UserSetupBasicResponse):
    """Schema for user setup with all related data"""
    roles_entities: List[UserSetupRolesEntityResponse] = []
    preferences: List[UserSetupPreferenceResponse] = []

    class Config:
        from_attributes = True


class UserSetupCreateWithDetails(BaseModel):
    """Schema for creating user setup with roles, entities, and preferences in one request"""
    basic: UserSetupBasicCreate
    roles_entities: Optional[UserSetupRolesEntityBase] = None
    preferences: Optional[UserSetupPreferenceBase] = None


# ============================================================================
# List Response Schemas
# ============================================================================

class UserSetupListResponse(BaseModel):
    """Schema for paginated user setup list"""
    total: int
    users: List[UserSetupBasicResponse]
    page: int
    page_size: int


# ============================================================================
# Dropdown/Reference Schemas
# ============================================================================

class UserReference(BaseModel):
    """Schema for user reference (for dropdowns)"""
    id: UUID
    username: str
    firstname: str
    lastname: str
    email: str
    status: str

    class Config:
        from_attributes = True


class AvailableUsersResponse(BaseModel):
    """Schema for available users list"""
    users: List[UserReference]

