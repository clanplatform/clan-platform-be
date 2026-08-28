"""
Schemas for the branch form's Education institution section.

This is the nested ``entities_education`` object carried inside a branch
(entities row / OnboardingBranch). It maps 1:1 to the fields shown on that
section of the branch form.

Backend-managed columns — ``id`` / ``entity_id`` / ``tenant_id`` / ``active`` /
``deleted`` — are intentionally absent from every schema.
"""
from typing import Optional, List
from datetime import datetime

from pydantic import BaseModel, Field


class EntitiesEducationBase(BaseModel):
    # Education institution
    institution_type: Optional[str] = Field(None, max_length=100, description="Institution type")
    students_enrolled: Optional[int] = Field(None, ge=0, description="Number of students enrolled")
    campuses: Optional[int] = Field(None, ge=0, description="Number of campuses")
    accreditation_body: Optional[str] = Field(None, max_length=100, description="Accreditation body, e.g. AACSB, regional")


class EntitiesEducationCreate(EntitiesEducationBase):
    pass


class EntitiesEducationUpdate(BaseModel):
    institution_type: Optional[str] = Field(None, max_length=100)
    students_enrolled: Optional[int] = Field(None, ge=0)
    campuses: Optional[int] = Field(None, ge=0)
    accreditation_body: Optional[str] = Field(None, max_length=100)


class EntitiesEducationResponse(EntitiesEducationBase):
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EntitiesEducationListResponse(BaseModel):
    entities_education: List[EntitiesEducationResponse]
    total: int
