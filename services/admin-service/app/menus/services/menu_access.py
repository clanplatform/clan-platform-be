"""
Cascades a menu's access-derived active state down to its forms.

Application/Module/Menu already derive their own is_active from their access
list ("disable" -> False, "write"/"read" -> True — see
app.core.access.is_active_from_access). This extends that one level further:
a menu's forms mirror the same active state, so disabling a menu also hides
its forms (and re-enabling the menu shows them again).
"""
from uuid import UUID

from sqlalchemy.orm import Session

from app.forms.models.forms import Form


def cascade_menu_active_state_to_forms(db: Session, menu_id: UUID, is_active: bool) -> int:
    """
    Set is_active on every (non-deleted) form under menu_id to match the
    menu's own access-derived active state. Returns the number of form rows
    changed (0 if none needed it).
    """
    changed = db.query(Form).filter(
        Form.menu_id == menu_id,
        Form.is_deleted == False,
        Form.is_active != is_active,
    ).update({"is_active": is_active}, synchronize_session=False)
    if changed:
        db.commit()
    return changed
