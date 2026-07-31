from pydantic import BaseModel, EmailStr, Field, field_validator, SecretStr
from typing import Optional, List
from uuid import UUID
from datetime import datetime


# ============================================================================
# UserSetupBasic Schemas
# ============================================================================

class UserSetupBasicBase(BaseModel):
    """Base schema for UserSetupBasic.

    tenant_id is intentionally omitted: it is derived from the JWT server-side,
    never sent in the request or returned in the response (consistent with the
    other admin-service modules).

    can_change_password is intentionally omitted: it is a backend-operational
    flag (always True at creation — forces the first-login password-change
    flow, consumed by the auth-service login flow), not a form field.

    entities (the array of assigned entity ids) is intentionally omitted: it is
    a backend fallback column read by audit context resolution; default_entity
    is the single source of truth exposed here ("Branch / location").
    """
    firstname: str = Field(..., min_length=1, max_length=100, description="First name")
    lastname: str = Field(..., min_length=1, max_length=100, description="Last name")
    employee_id: str = Field(..., min_length=1, max_length=50, description="Employee ID (unique)")
    username: str = Field(..., min_length=1, max_length=100, description="Username (unique)")
    email: EmailStr = Field(..., description="Email address (unique)")
    phone_number: Optional[str] = Field(None, max_length=20, description="Phone number")
    status: str = Field(default='active', max_length=50, description="Employment status")
    default_entity: Optional[UUID] = Field(None, description="Branch / location (entity) ID")
    role_id: Optional[UUID] = Field(None, description="Role assigned to this user (user_role.id)")
    user_group_id: Optional[UUID] = Field(None, description="User group id (bare reference)")
    send_invite_email: bool = Field(default=False, description="Send an invite email to the user")

    @field_validator('default_entity', 'user_group_id', 'role_id', mode='before')
    @classmethod
    def empty_str_to_none(cls, v):
        """Convert empty strings to None for UUID fields"""
        if v == '' or v == 'string':
            return None
        return v


class UserSetupBasicCreate(UserSetupBasicBase):
    """Schema for creating a new user setup"""
    password: str = Field(..., min_length=8, max_length=100, description="User password (will be hashed)")


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
    default_entity: Optional[UUID] = None
    role_id: Optional[UUID] = None
    user_group_id: Optional[UUID] = None
    send_invite_email: Optional[bool] = None

    @field_validator('default_entity', 'user_group_id', 'role_id', mode='before')
    @classmethod
    def empty_str_to_none(cls, v):
        """Convert empty strings to None for UUID fields"""
        if v == '' or v == 'string':
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
# UserSetupPreference Schemas
# ============================================================================

class UserSetupPreferenceBase(BaseModel):
    """Base schema for UserSetupPreference"""
    language: str = Field(default='en', max_length=10, description="Language preference")
    timezone: str = Field(default='UTC', max_length=50, description="Timezone preference")
    theme: str = Field(default='light', max_length=20, description="Theme preference")
    accent_color: str = Field(default='blue', max_length=50, description="Accent color preference")
    density: str = Field(default='comfortable', max_length=20, description="Density preference")

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
    usersetup_basic_id: UUID = Field(..., description="User setup basic ID")


class UserSetupPreferenceUpdate(BaseModel):
    """Schema for updating user preferences"""
    usersetup_basic_id: Optional[UUID] = None
    language: Optional[str] = Field(None, max_length=10)
    timezone: Optional[str] = Field(None, max_length=50)
    theme: Optional[str] = Field(None, max_length=20)
    accent_color: Optional[str] = Field(None, max_length=50)
    density: Optional[str] = Field(None, max_length=20)

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
    preferences: List[UserSetupPreferenceResponse] = []

    class Config:
        from_attributes = True


class UserSetupCreateWithDetails(BaseModel):
    """Schema for creating user setup with preferences in one request"""
    basic: UserSetupBasicCreate
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

