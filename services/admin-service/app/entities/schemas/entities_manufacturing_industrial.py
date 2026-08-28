"""
Schemas for the branch form's Manufacturing plant & production section.

This is the nested ``entities_manufacturing_industrial`` object carried inside
a branch (entities row / OnboardingBranch). It maps 1:1 to the fields shown on
that section of the branch form.

Backend-managed columns — ``id`` / ``entity_id`` / ``tenant_id`` / ``active`` /
``deleted`` — are intentionally absent from every schema.
"""
from typing import Optional, List
from datetime import datetime

from pydantic import BaseModel, Field


class EntitiesManufacturingIndustrialBase(BaseModel):
    # Manufacturing compliance documents (uploaded file references / URLs)
    iso_certificates_doc: Optional[str] = Field(None, max_length=500, description="ISO certificates")
    safety_osha_compliance_doc: Optional[str] = Field(None, max_length=500, description="Safety / OSHA compliance")
    environmental_permit_doc: Optional[str] = Field(None, max_length=500, description="Environmental permit")

    # Manufacturing plant & production
    plant_type: Optional[str] = Field(None, max_length=100, description="Plant type")
    production_lines: Optional[int] = Field(None, ge=0, description="Number of production lines")
    shift_pattern: Optional[str] = Field(None, max_length=100, description="Shift pattern")
    production_capacity: Optional[str] = Field(None, max_length=100, description="Production capacity, e.g. 10k units/day")
    iso_certifications: Optional[List[str]] = Field(None, description="ISO certifications held (multi-select)")
    erp_mes_system: Optional[str] = Field(None, max_length=150, description="ERP / MES system, e.g. SAP S/4HANA")
    handles_hazardous_materials: bool = Field(default=False, description="Handles hazardous materials")
    unionized_workforce: bool = Field(default=False, description="Unionized workforce")


class EntitiesManufacturingIndustrialCreate(EntitiesManufacturingIndustrialBase):
    pass


class EntitiesManufacturingIndustrialUpdate(BaseModel):
    iso_certificates_doc: Optional[str] = Field(None, max_length=500)
    safety_osha_compliance_doc: Optional[str] = Field(None, max_length=500)
    environmental_permit_doc: Optional[str] = Field(None, max_length=500)
    plant_type: Optional[str] = Field(None, max_length=100)
    production_lines: Optional[int] = Field(None, ge=0)
    shift_pattern: Optional[str] = Field(None, max_length=100)
    production_capacity: Optional[str] = Field(None, max_length=100)
    iso_certifications: Optional[List[str]] = None
    erp_mes_system: Optional[str] = Field(None, max_length=150)
    handles_hazardous_materials: Optional[bool] = None
    unionized_workforce: Optional[bool] = None


class EntitiesManufacturingIndustrialResponse(EntitiesManufacturingIndustrialBase):
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EntitiesManufacturingIndustrialListResponse(BaseModel):
    entities_manufacturing_industrial: List[EntitiesManufacturingIndustrialResponse]
    total: int
