"""
Subscription API endpoints — CRUD for a tenant's subscription plan, application/
module grants and add-on limits (the onboarding "Subscription plan" step).

tenant_id is taken from the caller's JWT (None for master-DB users), never the
request body, and is not returned in responses.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_tenant_db
from app.core.security import get_current_user
from app.infrastructure.audit_helpers import get_user_id
from app.subscription.services import subscription as subscription_service
from app.subscription.exceptions import SubscriptionNotFoundError
from app.subscription.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionUpdate,
    SubscriptionResponse,
    SubscriptionListResponse,
)

router = APIRouter()


def _creator_uuid(current_user) -> Optional[UUID]:
    uid = get_user_id(current_user)
    try:
        return UUID(str(uid)) if uid else None
    except (ValueError, TypeError):
        return None


def _tenant_from_token(current_user) -> Optional[UUID]:
    return current_user.get("tenant_id") if isinstance(current_user, dict) else None


@router.post(
    "/",
    response_model=SubscriptionResponse,
    status_code=201,
    summary="Create a subscription",
    description="Create a subscription. tenant_id is taken from the JWT (None for master-DB users).",
)
def create_subscription(
    subscription: SubscriptionCreate,
    db: Session = Depends(get_tenant_db),
    current_user=Depends(get_current_user),
):
    return subscription_service.create_subscription(
        db,
        subscription,
        tenant_id=_tenant_from_token(current_user),
        user_id=_creator_uuid(current_user),
    )


@router.get(
    "/",
    response_model=SubscriptionListResponse,
    summary="List subscriptions",
    description="Paginated list of subscriptions (newest first).",
)
def list_subscriptions(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_tenant_db),
    current_user=Depends(get_current_user),
):
    total = subscription_service.get_subscriptions_count(db)
    items = subscription_service.get_subscriptions(db, skip=(page - 1) * size, limit=size)
    return SubscriptionListResponse(
        subscriptions=items,
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size if size else 0,
    )


@router.get(
    "/{subscription_id}",
    response_model=SubscriptionResponse,
    summary="Get a subscription",
)
def get_subscription(
    subscription_id: UUID,
    db: Session = Depends(get_tenant_db),
    current_user=Depends(get_current_user),
):
    sub = subscription_service.get_subscription(db, subscription_id)
    if not sub:
        raise SubscriptionNotFoundError()
    return sub


@router.put(
    "/{subscription_id}",
    response_model=SubscriptionResponse,
    summary="Update a subscription",
)
def update_subscription(
    subscription_id: UUID,
    subscription: SubscriptionUpdate,
    db: Session = Depends(get_tenant_db),
    current_user=Depends(get_current_user),
):
    return subscription_service.update_subscription(
        db, subscription_id, subscription, user_id=_creator_uuid(current_user)
    )


@router.delete(
    "/{subscription_id}",
    summary="Delete a subscription",
    description="Soft delete (sets is_active = False).",
)
def delete_subscription(
    subscription_id: UUID,
    db: Session = Depends(get_tenant_db),
    current_user=Depends(get_current_user),
):
    if not subscription_service.delete_subscription(db, subscription_id, user_id=_creator_uuid(current_user)):
        raise SubscriptionNotFoundError()
    return {"message": "Subscription deleted successfully"}
