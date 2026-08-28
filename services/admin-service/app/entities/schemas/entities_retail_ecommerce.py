"""
Schemas for the branch form's Retail & store operations section.

This is the nested ``entities_retail_ecommerce`` object carried inside a branch
(entities row / OnboardingBranch). It maps 1:1 to the fields shown on that
section of the branch form.

Backend-managed columns — ``id`` / ``entity_id`` / ``tenant_id`` / ``active`` /
``deleted`` — are intentionally absent from every schema.
"""
from typing import Optional, List
from datetime import datetime

from pydantic import BaseModel, Field


class EntitiesRetailEcommerceBase(BaseModel):
    # Retail & store operations
    store_format: Optional[str] = Field(None, max_length=100, description="Store format")
    number_of_stores: Optional[int] = Field(None, ge=0, description="Number of stores")
    pos_terminals: Optional[int] = Field(None, ge=0, description="Number of POS terminals")
    pos_system: Optional[str] = Field(None, max_length=150, description="POS system, e.g. Square, Shopify")
    ecommerce_enabled: bool = Field(default=False, description="E-commerce enabled")
    loyalty_program: bool = Field(default=False, description="Loyalty program")


class EntitiesRetailEcommerceCreate(EntitiesRetailEcommerceBase):
    pass


class EntitiesRetailEcommerceUpdate(BaseModel):
    store_format: Optional[str] = Field(None, max_length=100)
    number_of_stores: Optional[int] = Field(None, ge=0)
    pos_terminals: Optional[int] = Field(None, ge=0)
    pos_system: Optional[str] = Field(None, max_length=150)
    ecommerce_enabled: Optional[bool] = None
    loyalty_program: Optional[bool] = None


class EntitiesRetailEcommerceResponse(EntitiesRetailEcommerceBase):
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EntitiesRetailEcommerceListResponse(BaseModel):
    entities_retail_ecommerce: List[EntitiesRetailEcommerceResponse]
    total: int
