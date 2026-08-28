"""
Sync helpers for a branch's nested ``entities_healthcare`` section.

The branch payload (EntityBase / OnboardingBranch) carries an optional
``entities_healthcare`` list. There is at most one healthcare-compliance row
per branch (unique on ``entity_id``), so the list is really an upsert channel:

    None   -> section not touched (no-op)
    []     -> soft-delete the branch's existing row, if any
    [item] -> upsert that item onto the branch's row (extra items are ignored
              with a warning)

None of these helpers commit — the caller (entity / onboarding service) owns
the transaction.
"""
import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.entities.models.entities_healthcare import EntitiesHealthcare
from app.entities.schemas.entities_healthcare import EntitiesHealthcareCreate

logger = logging.getLogger(__name__)

# The data columns an inbound item may set (everything on the Base schema).
_DATA_FIELDS = tuple(EntitiesHealthcareCreate.model_fields.keys())


def get_entities_healthcare_rows(db: Session, entity_id: UUID) -> List[EntitiesHealthcare]:
    """Live (non-deleted) healthcare-compliance rows for a branch (0 or 1)."""
    return (
        db.query(EntitiesHealthcare)
        .filter(EntitiesHealthcare.entity_id == entity_id, EntitiesHealthcare.deleted == False)  # noqa: E712
        .all()
    )


def _row_any_state(db: Session, entity_id: UUID) -> Optional[EntitiesHealthcare]:
    """The branch's healthcare-compliance row regardless of its deleted flag.

    The unique constraint is on ``entity_id`` alone, so a soft-deleted row still
    occupies that key — the upsert path must revive it rather than INSERT a
    second one.
    """
    return (
        db.query(EntitiesHealthcare)
        .filter(EntitiesHealthcare.entity_id == entity_id)
        .first()
    )


def soft_delete_entities_healthcare_rows(db: Session, entity_id: UUID) -> int:
    """Soft-delete the branch's healthcare-compliance row(s). Returns the count."""
    rows = get_entities_healthcare_rows(db, entity_id)
    for row in rows:
        row.deleted = True
        row.active = False
        db.add(row)
    return len(rows)


def sync_entities_healthcare_rows(
    db: Session,
    entity_id: UUID,
    tenant_id: Optional[UUID],
    rows: Optional[List[EntitiesHealthcareCreate]],
) -> None:
    """Upsert the branch's healthcare-compliance row from the nested payload.

    ``rows`` is whatever the branch payload carried for ``entities_healthcare``
    (list of schema items, ``[]``, or ``None``) — see the module docstring for
    the semantics of each.
    """
    if rows is None:
        return

    if len(rows) == 0:
        cleared = soft_delete_entities_healthcare_rows(db, entity_id)
        logger.info("[ENTITIES_HEALTHCARE] entity=%s cleared (%d row(s))", entity_id, cleared)
        return

    if len(rows) > 1:
        logger.warning(
            "[ENTITIES_HEALTHCARE] entity=%s got %d entities_healthcare items; using the first",
            entity_id, len(rows),
        )

    item = rows[0]
    data = item.model_dump()

    row = _row_any_state(db, entity_id)
    if row is not None:
        for field in _DATA_FIELDS:
            setattr(row, field, data.get(field))
        row.active = True
        row.deleted = False  # revive if it had been cleared
        db.add(row)
        logger.info("[ENTITIES_HEALTHCARE] entity=%s updated", entity_id)
    else:
        row = EntitiesHealthcare(
            entity_id=entity_id,
            tenant_id=tenant_id,
            **{field: data.get(field) for field in _DATA_FIELDS},
        )
        db.add(row)
        logger.info("[ENTITIES_HEALTHCARE] entity=%s created", entity_id)
