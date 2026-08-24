"""Subscription service — CRUD over the subscription table."""
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
import logging

from fastapi import HTTPException, status

from app.subscription.models.subscription import Subscription
from app.subscription.schemas.subscription import SubscriptionCreate, SubscriptionUpdate
from app.subscription.exceptions import SubscriptionNotFoundError
from app.infrastructure.audit_tenant import fire_audit_log
from app.infrastructure.database.session import SessionLocal
from app.applications.models.application import Application
from app.modules.models.module import Module

logger = logging.getLogger(__name__)


def _validate_grants(application_ids: Optional[List[UUID]], module_ids: Optional[List[UUID]]) -> None:
    """applications_to_grant must be real applications.id values, and every id
    in modules_to_grant must belong to one of those granted applications.

    applications/modules are master-catalog data (app.applications /
    app.modules), so this always checks against the master DB regardless of
    which DB the subscription row itself is being written to (a tenant-DB
    caller's own copy of these tables may only hold whatever's been synced
    on demand elsewhere — not the full catalog)."""
    if not application_ids and not module_ids:
        return
    application_id_set = set(application_ids or [])
    master_db = SessionLocal()
    try:
        if application_id_set:
            found_apps = {
                a.id for a in master_db.query(Application.id)
                .filter(Application.id.in_(application_id_set)).all()
            }
            missing_apps = application_id_set - found_apps
            if missing_apps:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Application(s) not found: {', '.join(str(a) for a in missing_apps)}",
                )

        if not module_ids:
            return
        modules = master_db.query(Module).filter(Module.id.in_(module_ids)).all()
        found_ids = {m.id for m in modules}
        missing = set(module_ids) - found_ids
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Module(s) not found: {', '.join(str(m) for m in missing)}",
            )
        mismatched = [m for m in modules if m.application_id not in application_id_set]
        if mismatched:
            names = ", ".join(f"{m.name} ({m.id})" for m in mismatched)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "modules_to_grant contains module(s) that don't belong to any "
                    f"application in applications_to_grant: {names}"
                ),
            )
    finally:
        master_db.close()


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
    _validate_grants(subscription.applications_to_grant, subscription.modules_to_grant)
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
    # Validate against the EFFECTIVE grants (this update merged onto whatever
    # wasn't touched), not just whatever happens to be in this partial payload.
    effective_apps = update_data.get("applications_to_grant", db_sub.applications_to_grant)
    effective_modules = update_data.get("modules_to_grant", db_sub.modules_to_grant)
    _validate_grants(effective_apps, effective_modules)

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
