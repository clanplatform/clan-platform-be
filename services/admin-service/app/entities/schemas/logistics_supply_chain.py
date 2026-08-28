"""
Schemas for the branch form's Logistics & supply chain section.

This is the nested ``logistics_supply_chain`` object carried inside a branch
(entities row / OnboardingBranch). It maps 1:1 to the fields shown on that
section of the branch form.

Backend-managed columns — ``id`` / ``entity_id`` / ``tenant_id`` / ``active`` /
``deleted`` — are intentionally absent from every schema.
"""
from typing import Optional, List
from datetime import datetime

from pydantic import BaseModel, Field


class LogisticsSupplyChainBase(BaseModel):
    # Logistics & supply chain
    fleet_size: Optional[str] = Field(None, max_length=100, description="Fleet size, e.g. 120 vehicles")
    warehouses_dcs: Optional[int] = Field(None, ge=0, description="Number of warehouses / distribution centres")
    transport_modes: Optional[List[str]] = Field(None, description="Transport modes used (multi-select)")
    wms_tms_system: Optional[str] = Field(None, max_length=150, description="WMS / TMS system, e.g. Manhattan, Blue Yonder")


class LogisticsSupplyChainCreate(LogisticsSupplyChainBase):
    pass


class LogisticsSupplyChainUpdate(BaseModel):
    fleet_size: Optional[str] = Field(None, max_length=100)
    warehouses_dcs: Optional[int] = Field(None, ge=0)
    transport_modes: Optional[List[str]] = None
    wms_tms_system: Optional[str] = Field(None, max_length=150)


class LogisticsSupplyChainResponse(LogisticsSupplyChainBase):
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LogisticsSupplyChainListResponse(BaseModel):
    logistics_supply_chain: List[LogisticsSupplyChainResponse]
    total: int
