from typing import List, Optional, Annotated
from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime
from decimal import Decimal
import uuid

# The precision constraints have to sit on the Decimal itself rather than on
# Optional[...] — pydantic 2.6 rejects max_digits applied to the union.
# Both mirror the DECIMAL(10,7) columns.
Latitude = Annotated[Decimal, Field(ge=-90, le=90, max_digits=10, decimal_places=7)]
Longitude = Annotated[Decimal, Field(ge=-180, le=180, max_digits=10, decimal_places=7)]


class MasterCityBase(BaseModel):
    state_id: uuid.UUID = Field(..., description="State this city belongs to")
    city_name: str = Field(..., min_length=1, max_length=100, description="City name", examples=["Bengaluru"])
    postal_code: Optional[str] = Field(None, max_length=20, description="Representative postal/ZIP code", examples=["560001"])
    latitude: Optional[Latitude] = Field(None, description="Latitude in decimal degrees", examples=["12.9715987"])
    longitude: Optional[Longitude] = Field(None, description="Longitude in decimal degrees", examples=["77.5945627"])
    display_order: Optional[int] = Field(0, ge=0, description="Sort order in pickers")
    is_active: Optional[bool] = Field(True, description="Whether the city is selectable")

    @field_validator("city_name", "postal_code")
    @classmethod
    def strip_text(cls, v):
        return v.strip() if isinstance(v, str) else v


class MasterCityCreate(MasterCityBase):
    pass


class MasterCityUpdate(BaseModel):
    state_id: Optional[uuid.UUID] = Field(None, description="Move the city to a different state")
    city_name: Optional[str] = Field(None, min_length=1, max_length=100, description="City name")
    postal_code: Optional[str] = Field(None, max_length=20, description="Representative postal/ZIP code")
    latitude: Optional[Latitude] = Field(None, description="Latitude in decimal degrees")
    longitude: Optional[Longitude] = Field(None, description="Longitude in decimal degrees")
    display_order: Optional[int] = Field(None, ge=0, description="Sort order in pickers")
    is_active: Optional[bool] = Field(None, description="Whether the city is selectable")

    @field_validator("city_name", "postal_code")
    @classmethod
    def strip_text(cls, v):
        return v.strip() if isinstance(v, str) else v


class MasterCityResponse(MasterCityBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MasterCityListResponse(BaseModel):
    cities: List[MasterCityResponse]
    total: int
    page: int
    size: int
    total_pages: int

    model_config = ConfigDict(from_attributes=True)
