"""
Subscription Pydantic schemas.

tenant_id is intentionally absent from every schema — it is derived from the
caller's JWT server-side (NULL for master-DB users), never sent in the request
or returned in the response.
"""
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict


class SubscriptionBase(BaseModel):
    # Subscription plan
    plan: Optional[str] = Field(None, max_length=50, description="Standard | Professional | Enterprise")
    billing_cycle: Optional[str] = Field(None, max_length=20, description="Annual | Monthly | Quarterly")
    licensed_user_seats: Optional[int] = Field(None, ge=0)
    start_as_trial: bool = Field(default=False)

    # Grants — ids of platform applications / modules to grant
    applications_to_grant: Optional[List[UUID]] = Field(default=None, description="Application ids to grant")
    modules_to_grant: Optional[List[UUID]] = Field(default=None, description="Module ids to grant")

    # Add-ons & limits
    extra_storage: Optional[str] = Field(None, max_length=50, description="Extra storage add-on, e.g. '50GB'")
    support_tier: Optional[str] = Field(None, max_length=50)
    api_access: bool = Field(default=False)
    sandbox_environment: bool = Field(default=False)
    white_label_branding: bool = Field(default=False)

    # is_active is intentionally NOT part of the schema — it is
    # operational/backend-managed (defaulted True on create, toggled by
    # delete/restore) and never accepted or returned here.


class SubscriptionCreate(SubscriptionBase):
    pass


class SubscriptionUpdate(BaseModel):
    plan: Optional[str] = Field(None, max_length=50)
    billing_cycle: Optional[str] = Field(None, max_length=20)
    licensed_user_seats: Optional[int] = Field(None, ge=0)
    start_as_trial: Optional[bool] = None
    applications_to_grant: Optional[List[UUID]] = None
    modules_to_grant: Optional[List[UUID]] = None
    extra_storage: Optional[str] = Field(None, max_length=50)
    support_tier: Optional[str] = Field(None, max_length=50)
    api_access: Optional[bool] = None
    sandbox_environment: Optional[bool] = None
    white_label_branding: Optional[bool] = None


class SubscriptionResponse(SubscriptionBase):
    subscription_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubscriptionListResponse(BaseModel):
    subscriptions: List[SubscriptionResponse]
    total: int
    page: int
    size: int
    pages: int
