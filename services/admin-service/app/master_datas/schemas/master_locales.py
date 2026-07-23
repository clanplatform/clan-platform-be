from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime
import uuid

# locale_code is the same kind of BCP 47 tag as master_languages.locale, so it
# reuses that normaliser — "en_us" and "EN-us" must not both slip past the
# unique constraint as distinct rows.
from app.master_datas.schemas.master_languages import normalize_locale_tag


class MasterLocaleBase(BaseModel):
    locale_code: str = Field(..., min_length=2, max_length=20, description="BCP 47 locale tag", examples=["en-US"])
    locale_name: str = Field(..., min_length=1, max_length=100, description="Human-readable locale name", examples=["English (United States)"])
    language_id: uuid.UUID = Field(..., description="Language this locale is based on")
    country_id: Optional[uuid.UUID] = Field(None, description="Country/region, omitted for language-only locales")
    date_format: Optional[str] = Field(None, max_length=30, description="Date display pattern", examples=["MM/DD/YYYY"])
    time_format: Optional[str] = Field(None, max_length=20, description="Time display pattern", examples=["hh:mm A"])
    number_format: Optional[str] = Field(None, max_length=30, description="Number display pattern", examples=["#,##0.00"])
    is_default: Optional[bool] = Field(False, description="Whether this is the default locale (only one may be set)")
    is_active: Optional[bool] = Field(True, description="Whether the locale is selectable")

    @field_validator("locale_code")
    @classmethod
    def normalize_code(cls, v):
        return normalize_locale_tag(v)

    @field_validator("locale_name", "date_format", "time_format", "number_format")
    @classmethod
    def strip_text(cls, v):
        return v.strip() if isinstance(v, str) else v


class MasterLocaleCreate(MasterLocaleBase):
    pass


class MasterLocaleUpdate(BaseModel):
    locale_code: Optional[str] = Field(None, min_length=2, max_length=20, description="BCP 47 locale tag")
    locale_name: Optional[str] = Field(None, min_length=1, max_length=100, description="Human-readable locale name")
    language_id: Optional[uuid.UUID] = Field(None, description="Language this locale is based on")
    country_id: Optional[uuid.UUID] = Field(None, description="Country/region, omitted for language-only locales")
    date_format: Optional[str] = Field(None, max_length=30, description="Date display pattern")
    time_format: Optional[str] = Field(None, max_length=20, description="Time display pattern")
    number_format: Optional[str] = Field(None, max_length=30, description="Number display pattern")
    is_default: Optional[bool] = Field(None, description="Whether this is the default locale")
    is_active: Optional[bool] = Field(None, description="Whether the locale is selectable")

    @field_validator("locale_code")
    @classmethod
    def normalize_code(cls, v):
        return normalize_locale_tag(v)

    @field_validator("locale_name", "date_format", "time_format", "number_format")
    @classmethod
    def strip_text(cls, v):
        return v.strip() if isinstance(v, str) else v


class MasterLocaleResponse(MasterLocaleBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MasterLocaleListResponse(BaseModel):
    locales: List[MasterLocaleResponse]
    total: int
    page: int
    size: int
    total_pages: int

    model_config = ConfigDict(from_attributes=True)
