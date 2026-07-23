from typing import List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime
import re
import uuid

TextDirection = Literal["ltr", "rtl"]

# "en-US" / "en_us" style tags get normalised to lower-UPPER. Richer IETF tags
# (zh-Hans-CN) are left alone — their script subtag is Titlecase, not upper.
_SIMPLE_LOCALE = re.compile(r"^([A-Za-z]{2,3})[-_]([A-Za-z]{2})$")
_BARE_LOCALE = re.compile(r"^[A-Za-z]{2,3}$")


def normalize_locale_tag(v):
    """Shared by master_locales.locale_code — keep both tags in one canonical form."""
    if not isinstance(v, str):
        return v
    v = v.strip()
    if not v:
        return None
    m = _SIMPLE_LOCALE.match(v)
    if m:
        return f"{m.group(1).lower()}-{m.group(2).upper()}"
    if _BARE_LOCALE.match(v):
        return v.lower()
    return v


def _normalize_iso(v):
    if v is None:
        return v
    v = v.strip().lower()
    if not v.isalpha():
        raise ValueError("Code must contain letters only")
    return v


class MasterLanguageBase(BaseModel):
    language_name: str = Field(..., min_length=1, max_length=100, description="Language name in English", examples=["Hindi"])
    native_name: Optional[str] = Field(None, max_length=100, description="Language name in its own script", examples=["हिन्दी"])
    iso639_1: str = Field(..., min_length=2, max_length=2, description="ISO 639-1 two-letter code (lowercase)", examples=["hi"])
    iso639_2: Optional[str] = Field(None, min_length=3, max_length=3, description="ISO 639-2 three-letter code (lowercase)", examples=["hin"])
    locale: Optional[str] = Field(None, max_length=20, description="BCP 47 locale tag", examples=["hi-IN"])
    text_direction: Optional[TextDirection] = Field("ltr", description="Script direction: ltr or rtl")
    display_order: Optional[int] = Field(0, ge=0, description="Sort order in pickers")
    is_default: Optional[bool] = Field(False, description="Whether this is the default language (only one may be set)")
    is_active: Optional[bool] = Field(True, description="Whether the language is selectable")

    @field_validator("iso639_1", "iso639_2")
    @classmethod
    def normalize_iso(cls, v):
        return _normalize_iso(v)

    @field_validator("locale")
    @classmethod
    def normalize_locale(cls, v):
        return normalize_locale_tag(v)

    @field_validator("language_name", "native_name")
    @classmethod
    def strip_text(cls, v):
        return v.strip() if isinstance(v, str) else v


class MasterLanguageCreate(MasterLanguageBase):
    pass


class MasterLanguageUpdate(BaseModel):
    language_name: Optional[str] = Field(None, min_length=1, max_length=100, description="Language name in English")
    native_name: Optional[str] = Field(None, max_length=100, description="Language name in its own script")
    iso639_1: Optional[str] = Field(None, min_length=2, max_length=2, description="ISO 639-1 two-letter code")
    iso639_2: Optional[str] = Field(None, min_length=3, max_length=3, description="ISO 639-2 three-letter code")
    locale: Optional[str] = Field(None, max_length=20, description="BCP 47 locale tag")
    text_direction: Optional[TextDirection] = Field(None, description="Script direction: ltr or rtl")
    display_order: Optional[int] = Field(None, ge=0, description="Sort order in pickers")
    is_default: Optional[bool] = Field(None, description="Whether this is the default language")
    is_active: Optional[bool] = Field(None, description="Whether the language is selectable")

    @field_validator("iso639_1", "iso639_2")
    @classmethod
    def normalize_iso(cls, v):
        return _normalize_iso(v)

    @field_validator("locale")
    @classmethod
    def normalize_locale(cls, v):
        return normalize_locale_tag(v)

    @field_validator("language_name", "native_name")
    @classmethod
    def strip_text(cls, v):
        return v.strip() if isinstance(v, str) else v


class MasterLanguageResponse(MasterLanguageBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MasterLanguageListResponse(BaseModel):
    languages: List[MasterLanguageResponse]
    total: int
    page: int
    size: int
    total_pages: int

    model_config = ConfigDict(from_attributes=True)
