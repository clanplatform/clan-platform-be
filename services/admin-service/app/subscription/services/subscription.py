"""Subscription service — CRUD over the subscription table."""
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
import logging

from app.subscription.models.subscription import Subscription
from app.subscription.schemas.subscription import SubscriptionCreate, SubscriptionUpdate
from app.subscription.exceptions import SubscriptionNotFoundError
from app.infrastructure.audit_tenant import fire_audit_log

logger = logging.getLogger(__name__)


def _audit(action: str, sub: Subscription, user_id: Optional[UUID], **kw) -> None:
    """Best-effort audit — never breaks the caller."""
    try:
        fire_audit_log(
            action=action,
            object_type="Subscription",
            object_id=str(sub.subscription_id),
            tenant_id=str(sub.tenant_id) if sub.tenant_id else None,
            user_id=str(user_id) if user_id else None,
            **kw,
        )
    except Exception:  # pragma: no cover - audit must not fail the request
        pass


def get_subscription(db: Session, subscription_id: UUID) -> Optional[Subscription]:
    """Get a subscription by id."""
    return db.query(Subscription).filter(
        Subscription.subscription_id == subscription_id
    ).first()


def get_subscriptions(db: Session, skip: int = 0, limit: int = 100) -> List[Subscription]:
    """List subscriptions (newest first)."""
    return (
        db.query(Subscription)
        .order_by(Subscription.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_subscriptions_count(db: Session) -> int:
    return db.query(Subscription).count()


def create_subscription(
    db: Session,
    subscription: SubscriptionCreate,
    tenant_id: Optional[UUID],
    user_id: Optional[UUID] = None,
) -> Subscription:
    """Create a subscription.

    tenant_id is not part of the request body — it is derived from the caller's
    JWT (None for master-DB users, a tenant UUID for tenant-DB users).
    """
    db_sub = Subscription(
        **subscription.model_dump(),
        tenant_id=tenant_id,
        created_by=user_id,
    )
    db.add(db_sub)
    db.commit()
    db.refresh(db_sub)
    _audit("CREATE", db_sub, user_id, new_values={"plan": db_sub.plan, "billing_cycle": db_sub.billing_cycle})
    return db_sub


def update_subscription(
    db: Session,
    subscription_id: UUID,
    subscription: SubscriptionUpdate,
    user_id: Optional[UUID] = None,
) -> Subscription:
    """Update a subscription."""
    db_sub = get_subscription(db, subscription_id)
    if not db_sub:
        raise SubscriptionNotFoundError()

    update_data = subscription.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_sub, field, value)

    db.add(db_sub)
    db.commit()
    db.refresh(db_sub)
    _audit("UPDATE", db_sub, user_id, new_values=update_data)
    return db_sub


def delete_subscription(db: Session, subscription_id: UUID, user_id: Optional[UUID] = None) -> bool:
    """Soft delete a subscription (is_active = False)."""
    db_sub = get_subscription(db, subscription_id)
    if not db_sub:
        return False

    db_sub.is_active = False
    db.add(db_sub)
    db.commit()
    _audit("DELETE", db_sub, user_id, old_values={"is_active": True}, new_values={"is_active": False})
    return True
