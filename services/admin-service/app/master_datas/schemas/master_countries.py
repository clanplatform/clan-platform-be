from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime
import uuid


class MasterCountryBase(BaseModel):
    country_name: str = Field(..., min_length=1, max_length=100, description="Official country name", examples=["India"])
    iso2_code: str = Field(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2 code", examples=["IN"])
    iso3_code: str = Field(..., min_length=3, max_length=3, description="ISO 3166-1 alpha-3 code", examples=["IND"])
    numeric_code: Optional[int] = Field(None, ge=1, le=999, description="ISO 3166-1 numeric code", examples=[356])
    phone_code: Optional[str] = Field(None, max_length=10, description="International dialling prefix", examples=["+91"])
    currency_code: Optional[str] = Field(None, min_length=3, max_length=3, description="ISO 4217 currency code", examples=["INR"])
    timezone: Optional[str] = Field(None, max_length=100, description="Primary IANA timezone", examples=["Asia/Kolkata"])
    nationality: Optional[str] = Field(None, max_length=100, description="Demonym for the country", examples=["Indian"])
    flag_emoji: Optional[str] = Field(None, max_length=10, description="Flag emoji", examples=["🇮🇳"])
    display_order: Optional[int] = Field(0, ge=0, description="Sort order in pickers")
    is_default: Optional[bool] = Field(False, description="Whether this is the default country (only one may be set)")
    is_active: Optional[bool] = Field(True, description="Whether the country is selectable")

    @field_validator("iso2_code", "iso3_code", "currency_code")
    @classmethod
    def normalize_codes(cls, v):
        if v is None:
            return v
        v = v.strip().upper()
        if not v.isalpha():
            raise ValueError("Code must contain letters only")
        return v

    @field_validator("country_name", "nationality", "timezone", "phone_code")
    @classmethod
    def strip_text(cls, v):
        return v.strip() if isinstance(v, str) else v


class MasterCountryCreate(MasterCountryBase):
    pass


class MasterCountryUpdate(BaseModel):
    country_name: Optional[str] = Field(None, min_length=1, max_length=100, description="Official country name")
    iso2_code: Optional[str] = Field(None, min_length=2, max_length=2, description="ISO 3166-1 alpha-2 code")
    iso3_code: Optional[str] = Field(None, min_length=3, max_length=3, description="ISO 3166-1 alpha-3 code")
    numeric_code: Optional[int] = Field(None, ge=1, le=999, description="ISO 3166-1 numeric code")
    phone_code: Optional[str] = Field(None, max_length=10, description="International dialling prefix")
    currency_code: Optional[str] = Field(None, min_length=3, max_length=3, description="ISO 4217 currency code")
    timezone: Optional[str] = Field(None, max_length=100, description="Primary IANA timezone")
    nationality: Optional[str] = Field(None, max_length=100, description="Demonym for the country")
    flag_emoji: Optional[str] = Field(None, max_length=10, description="Flag emoji")
    display_order: Optional[int] = Field(None, ge=0, description="Sort order in pickers")
    is_default: Optional[bool] = Field(None, description="Whether this is the default country")
    is_active: Optional[bool] = Field(None, description="Whether the country is selectable")

    @field_validator("iso2_code", "iso3_code", "currency_code")
    @classmethod
    def normalize_codes(cls, v):
        if v is None:
            return v
        v = v.strip().upper()
        if not v.isalpha():
            raise ValueError("Code must contain letters only")
        return v

    @field_validator("country_name", "nationality", "timezone", "phone_code")
    @classmethod
    def strip_text(cls, v):
        return v.strip() if isinstance(v, str) else v


class MasterCountryResponse(MasterCountryBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MasterCountryListResponse(BaseModel):
    countries: List[MasterCountryResponse]
    total: int
    page: int
    size: int
    total_pages: int

    model_config = ConfigDict(from_attributes=True)
