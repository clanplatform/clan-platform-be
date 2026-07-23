from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime
import uuid


class MasterStateBase(BaseModel):
    country_id: uuid.UUID = Field(..., description="Country this state belongs to")
    state_name: str = Field(..., min_length=1, max_length=100, description="State or province name", examples=["Karnataka"])
    state_code: Optional[str] = Field(None, min_length=1, max_length=20, description="State code, unique within the country", examples=["KA"])
    capital: Optional[str] = Field(None, max_length=100, description="Capital city", examples=["Bengaluru"])
    display_order: Optional[int] = Field(0, ge=0, description="Sort order in pickers")
    is_active: Optional[bool] = Field(True, description="Whether the state is selectable")

    @field_validator("state_code")
    @classmethod
    def normalize_code(cls, v):
        return v.strip().upper() if isinstance(v, str) else v

    @field_validator("state_name", "capital")
    @classmethod
    def strip_text(cls, v):
        return v.strip() if isinstance(v, str) else v


class MasterStateCreate(MasterStateBase):
    pass


class MasterStateUpdate(BaseModel):
    country_id: Optional[uuid.UUID] = Field(None, description="Move the state to a different country")
    state_name: Optional[str] = Field(None, min_length=1, max_length=100, description="State or province name")
    state_code: Optional[str] = Field(None, min_length=1, max_length=20, description="State code, unique within the country")
    capital: Optional[str] = Field(None, max_length=100, description="Capital city")
    display_order: Optional[int] = Field(None, ge=0, description="Sort order in pickers")
    is_active: Optional[bool] = Field(None, description="Whether the state is selectable")

    @field_validator("state_code")
    @classmethod
    def normalize_code(cls, v):
        return v.strip().upper() if isinstance(v, str) else v

    @field_validator("state_name", "capital")
    @classmethod
    def strip_text(cls, v):
        return v.strip() if isinstance(v, str) else v


class MasterStateResponse(MasterStateBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MasterStateListResponse(BaseModel):
    states: List[MasterStateResponse]
    total: int
    page: int
    size: int
    total_pages: int

    model_config = ConfigDict(from_attributes=True)
