"""
Schemas for the branch form's Financial services & regulation section.

This is the nested ``entities_banking_financial`` object carried inside a branch
(entities row / OnboardingBranch). It maps 1:1 to the fields shown on that
section of the branch form.

Backend-managed columns — ``id`` / ``entity_id`` / ``tenant_id`` / ``active`` /
``deleted`` — are intentionally absent from every schema.
"""
from typing import Optional, List
from datetime import datetime

from pydantic import BaseModel, Field


class EntitiesBankingFinancialBase(BaseModel):
    # Financial services compliance documents (uploaded file references / URLs)
    regulatory_license_doc: Optional[str] = Field(None, max_length=500, description="Regulatory license")
    aml_kyc_policy_doc: Optional[str] = Field(None, max_length=500, description="AML / KYC policy")
    pci_dss_attestation_doc: Optional[str] = Field(None, max_length=500, description="PCI-DSS attestation of compliance")

    # Financial services & regulation
    primary_regulator: Optional[str] = Field(None, max_length=100, description="Primary regulator, e.g. SEC, FCA, RBI")
    license_type: Optional[str] = Field(None, max_length=100, description="License type")
    license_number: Optional[str] = Field(None, max_length=100, description="Regulatory license number")
    aml_compliance_officer: Optional[str] = Field(None, max_length=200, description="AML / compliance officer full name")
    kyc_level: Optional[str] = Field(None, max_length=50, description="KYC level")
    pci_dss_in_scope: bool = Field(default=False, description="PCI-DSS in scope")


class EntitiesBankingFinancialCreate(EntitiesBankingFinancialBase):
    pass


class EntitiesBankingFinancialUpdate(BaseModel):
    regulatory_license_doc: Optional[str] = Field(None, max_length=500)
    aml_kyc_policy_doc: Optional[str] = Field(None, max_length=500)
    pci_dss_attestation_doc: Optional[str] = Field(None, max_length=500)
    primary_regulator: Optional[str] = Field(None, max_length=100)
    license_type: Optional[str] = Field(None, max_length=100)
    license_number: Optional[str] = Field(None, max_length=100)
    aml_compliance_officer: Optional[str] = Field(None, max_length=200)
    kyc_level: Optional[str] = Field(None, max_length=50)
    pci_dss_in_scope: Optional[bool] = None


class EntitiesBankingFinancialResponse(EntitiesBankingFinancialBase):
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EntitiesBankingFinancialListResponse(BaseModel):
    entities_banking_financial: List[EntitiesBankingFinancialResponse]
    total: int
