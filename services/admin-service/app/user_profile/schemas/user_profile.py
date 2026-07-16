from typing import Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

# Allowed value sets for the constrained appearance fields.
ThemeType = Literal["light", "dark"]
DensityType = Literal["compact", "comfortable", "spacious"]
DirectionType = Literal["ltr", "rtl"]


class UserProfileBase(BaseModel):
    theme: ThemeType = Field("light", description="UI theme: light or dark")
    accent_color: str = Field("blue", max_length=50, description="Accent colour, e.g. blue")
    density: DensityType = Field("comfortable", description="Layout density: compact, comfortable or spacious")
    language: str = Field("English", max_length=50, description="Preferred language, e.g. English")
    direction: DirectionType = Field("ltr", description="Text direction: ltr or rtl")
    can_change_password: bool = Field(True, description="Whether the user is allowed to change their own password (mirrors usersetup_basic.can_change_password)")
    session: Optional[str] = Field(None, max_length=255, description="Active session token / identifier")
    is_active: Optional[bool] = Field(True, description="Whether the profile is active")


class UserProfileCreate(UserProfileBase):
    user_id: uuid.UUID = Field(..., description="Owner user ID (usersetup_basic.id) — one profile per user")
    tenant_id: Optional[uuid.UUID] = Field(None, description="Tenant this user belongs to (NULL for platform users)")


class UserProfileUpdate(BaseModel):
    theme: Optional[ThemeType] = Field(None, description="UI theme: light or dark")
    accent_color: Optional[str] = Field(None, max_length=50, description="Accent colour, e.g. blue")
    density: Optional[DensityType] = Field(None, description="Layout density: compact, comfortable or spacious")
    language: Optional[str] = Field(None, max_length=50, description="Preferred language, e.g. English")
    direction: Optional[DirectionType] = Field(None, description="Text direction: ltr or rtl")
    can_change_password: Optional[bool] = Field(None, description="Whether the user is allowed to change their own password")
    session: Optional[str] = Field(None, max_length=255, description="Active session token / identifier")
    is_active: Optional[bool] = Field(None, description="Whether the profile is active")


class UserProfileResponse(UserProfileBase):
    user_profile_id: uuid.UUID
    user_id: uuid.UUID
    tenant_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
