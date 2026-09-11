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

    entity_id holds every branch/location this user is assigned to (a user can
    belong to multiple entities). The first element is treated as the user's
    default/primary branch by audit context resolution.

    department_id / division_id are intentionally omitted here: they are
    backend-derived from job_code_id (job_codes -> jobcode_basicinfo's
    department_id/division_id), never accepted or returned directly. The
    columns still exist on usersetup_basic (see the model) for the
    access_scope filtering in scope_helpers.py.
    """
    firstname: str = Field(..., min_length=1, max_length=100, description="First name")
    lastname: str = Field(..., min_length=1, max_length=100, description="Last name")
    employee_id: str = Field(..., min_length=1, max_length=50, description="Employee ID (unique)")
    username: str = Field(..., min_length=1, max_length=100, description="Username (unique)")
    email: EmailStr = Field(..., description="Email address (unique)")
    phone_number: Optional[str] = Field(None, max_length=20, description="Phone number")
    profile_image_url: Optional[str] = Field(None, max_length=500, description="Profile image URL")
    status: str = Field(default='active', max_length=50, description="Employment status")
    entity_id: Optional[List[UUID]] = Field(None, description="Branch(es) / location(s) this user belongs to (entities.entity_id); first is the default")
    job_code_id: Optional[UUID] = Field(None, description="Job code assigned to this user (job_codes.id) — department_id/division_id are derived from it server-side")
    role_id: Optional[UUID] = Field(None, description="Role assigned to this user (user_role.id)")
    user_group_id: Optional[UUID] = Field(None, description="User group id (bare reference)")
    send_invite_email: bool = Field(default=False, description="Send an invite email to the user")

    @field_validator('user_group_id', 'role_id', 'job_code_id', mode='before')
    @classmethod
    def empty_str_to_none(cls, v):
        """Convert empty strings to None for UUID fields"""
        if v == '' or v == 'string':
            return None
        return v

    @field_validator('entity_id', mode='before')
    @classmethod
    def empty_list_to_none(cls, v):
        """Convert empty lists or lists with empty/placeholder strings to None"""
        if v == [] or v == [''] or v == ['string']:
            return None
        return v


class UserSetupBasicCreate(UserSetupBasicBase):
    """Schema for creating a new user setup.

    No password field — creation always server-generates a temporary
    password (see UserSetupService.create_user_setup_with_details), hashed
    and stored, synced to auth-service, and emailed to the user when
    send_invite_email is set (send_user_invitation_email). The plaintext is
    never accepted from the caller and never returned in the API response —
    same convention as onboarding's users[] (see
    app.onboarding.services.onboarding._create_user_row)."""
    pass


class UserSetupBasicUpdate(BaseModel):
    """Schema for updating user setup (all fields optional)"""
    firstname: Optional[str] = Field(None, min_length=1, max_length=100)
    lastname: Optional[str] = Field(None, min_length=1, max_length=100)
    employee_id: Optional[str] = Field(None, min_length=1, max_length=50)
    username: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = Field(None, max_length=20)
    profile_image_url: Optional[str] = Field(None, max_length=500)
    password: Optional[str] = Field(None, min_length=8, max_length=100, description="New password (will be hashed)")
    status: Optional[str] = Field(None, max_length=50)
    entity_id: Optional[List[UUID]] = None
    job_code_id: Optional[UUID] = Field(None, description="Job code assigned to this user (job_codes.id) — department_id/division_id are re-derived from it server-side when changed")
    role_id: Optional[UUID] = None
    user_group_id: Optional[UUID] = None
    send_invite_email: Optional[bool] = None

    @field_validator('user_group_id', 'role_id', 'job_code_id', mode='before')
    @classmethod
    def empty_str_to_none(cls, v):
        """Convert empty strings to None for UUID fields"""
        if v == '' or v == 'string':
            return None
        return v

    @field_validator('entity_id', mode='before')
    @classmethod
    def empty_list_to_none(cls, v):
        """Convert empty lists or lists with empty/placeholder strings to None"""
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
# UserSetupPreference Schemas
# ============================================================================

class UserSetupPreferenceBase(BaseModel):
    """Base schema for UserSetupPreference"""
    language: str = Field(default='en', max_length=10, description="Language preference")
    timezone: str = Field(default='UTC', max_length=50, description="Timezone preference")
    theme: str = Field(default='light', max_length=20, description="Theme preference")
    accent_color: str = Field(default='blue', max_length=50, description="Accent color preference")
    density: str = Field(default='comfortable', max_length=20, description="Density preference")
    text_direction: str = Field(default='ltr', max_length=3, description="Text direction: ltr or rtl (follows language automatically)")

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

    @field_validator('text_direction')
    @classmethod
    def validate_text_direction(cls, v):
        """Validate text direction"""
        valid_directions = ['ltr', 'rtl']
        if v not in valid_directions:
            raise ValueError(f"Text direction must be one of: {', '.join(valid_directions)}")
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
    text_direction: Optional[str] = Field(None, max_length=3)

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

    @field_validator('text_direction')
    @classmethod
    def validate_text_direction(cls, v):
        """Validate text direction"""
        if v is not None:
            valid_directions = ['ltr', 'rtl']
            if v not in valid_directions:
                raise ValueError(f"Text direction must be one of: {', '.join(valid_directions)}")
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

