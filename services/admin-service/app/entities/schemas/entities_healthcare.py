"""
Schemas for the branch form's Healthcare facility & compliance section.

This is the nested ``entities_healthcare`` object carried inside a branch
(entities row / OnboardingBranch). It maps 1:1 to the fields shown on that
section of the branch form.

Backend-managed columns — ``id`` / ``entity_id`` / ``tenant_id`` / ``active`` /
``deleted`` — are intentionally absent from every schema: ``entity_id`` /
``tenant_id`` are set from the owning branch and the caller's JWT, the rest are
lifecycle flags the service manages.
"""
from typing import Optional, List
from datetime import date, datetime

from pydantic import BaseModel, Field


class EntitiesHealthcareBase(BaseModel):
    # Healthcare compliance documents (uploaded file references / URLs)
    facility_license_doc: Optional[str] = Field(None, max_length=500, description="Facility license")
    accreditation_certificate_doc: Optional[str] = Field(None, max_length=500, description="Accreditation certificate")
    dea_registration_doc: Optional[str] = Field(None, max_length=500, description="DEA / controlled-substance registration")
    hipaa_compliance_attestation_doc: Optional[str] = Field(None, max_length=500, description="HIPAA compliance attestation")

    # Healthcare facility & compliance
    facility_type: Optional[str] = Field(None, max_length=100, description="Facility type")
    npi_number: Optional[str] = Field(None, max_length=50, description="National Provider Identifier")
    facility_license_no: Optional[str] = Field(None, max_length=100, description="Facility license number")
    license_expiry: Optional[date] = Field(None, description="Facility license expiry date")
    accreditation: Optional[str] = Field(None, max_length=100, description="Accreditation body")
    bed_capacity: Optional[int] = Field(None, ge=0, description="Bed capacity")
    licensed_practitioners: Optional[int] = Field(None, ge=0, description="Number of licensed practitioners")
    ehr_emr_system: Optional[str] = Field(None, max_length=150, description="EHR / EMR system, e.g. Epic, Cerner")
    hipaa_privacy_officer: Optional[str] = Field(None, max_length=200, description="HIPAA privacy officer full name")
    officer_email: Optional[str] = Field(None, max_length=255, description="HIPAA privacy officer email")
    telehealth_enabled: bool = Field(default=False, description="Telehealth enabled")
    handles_phi: bool = Field(default=False, description="Handles PHI (HIPAA)")


class EntitiesHealthcareCreate(EntitiesHealthcareBase):
    pass


class EntitiesHealthcareUpdate(BaseModel):
    facility_license_doc: Optional[str] = Field(None, max_length=500)
    accreditation_certificate_doc: Optional[str] = Field(None, max_length=500)
    dea_registration_doc: Optional[str] = Field(None, max_length=500)
    hipaa_compliance_attestation_doc: Optional[str] = Field(None, max_length=500)
    facility_type: Optional[str] = Field(None, max_length=100)
    npi_number: Optional[str] = Field(None, max_length=50)
    facility_license_no: Optional[str] = Field(None, max_length=100)
    license_expiry: Optional[date] = None
    accreditation: Optional[str] = Field(None, max_length=100)
    bed_capacity: Optional[int] = Field(None, ge=0)
    licensed_practitioners: Optional[int] = Field(None, ge=0)
    ehr_emr_system: Optional[str] = Field(None, max_length=150)
    hipaa_privacy_officer: Optional[str] = Field(None, max_length=200)
    officer_email: Optional[str] = Field(None, max_length=255)
    telehealth_enabled: Optional[bool] = None
    handles_phi: Optional[bool] = None


class EntitiesHealthcareResponse(EntitiesHealthcareBase):
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EntitiesHealthcareListResponse(BaseModel):
    entities_healthcare: List[EntitiesHealthcareResponse]
    total: int
