"""
Access-scope resolution and query filters for org-structure list endpoints
(entities, departments, divisions, usersetup_basic users).

A role's access_scope (see app.user_role.schemas.user_role.ACCESS_SCOPE_VALUES)
determines what the role's users can see:
  - whole_organization -> no restriction (default, unchanged behaviour)
  - branch_entity       -> only data under the user's assigned entities
  - department          -> only data under the user's assigned departments
  - division            -> only data under the user's assigned divisions

A user can be assigned multiple entities/departments/divisions (all are
UUID[] columns on usersetup_basic), so e.g. a branch_entity-scoped user
with two entities sees both entities' data.
"""
from dataclasses import dataclass, field
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session, Query


@dataclass
class ScopeFilter:
    scope: Optional[str] = None
    entity_ids: List[UUID] = field(default_factory=list)
    department_ids: List[UUID] = field(default_factory=list)
    division_ids: List[UUID] = field(default_factory=list)

    @property
    def is_restricted(self) -> bool:
        """whole_organization (or no scope/role resolved) means no restriction —
        this only ever narrows visibility for roles that explicitly set a
        scope; it never restricts anything that wasn't already restricted."""
        return self.scope in ("branch_entity", "department", "division")


def resolve_scope_filter(db: Session, user_id: Optional[str]) -> ScopeFilter:
    """
    Resolve the acting user's role access_scope plus their assigned
    entity/department/division IDs.

    Fails open (no restriction) on any error or missing data — same
    fail-open behaviour as get_audit_org_context.
    """
    if not user_id:
        return ScopeFilter()
    try:
        from app.user_setup.models.user_setup import UserSetupBasic
        from app.user_role.models.user_role import UserRoleBasic

        user_row = db.query(
            UserSetupBasic.role_id,
            UserSetupBasic.entity_id,
            UserSetupBasic.department_id,
            UserSetupBasic.division_id,
        ).filter(UserSetupBasic.id == user_id).first()
        if not user_row or not user_row.role_id:
            return ScopeFilter()

        role_row = db.query(UserRoleBasic.access_scope).filter(
            UserRoleBasic.user_role_id == user_row.role_id
        ).first()
        if not role_row:
            return ScopeFilter()

        return ScopeFilter(
            scope=role_row.access_scope,
            entity_ids=list(user_row.entity_id or []),
            department_ids=list(user_row.department_id or []),
            division_ids=list(user_row.division_id or []),
        )
    except Exception:
        db.rollback()
        return ScopeFilter()


def scoped_entity_ids(db: Session, sf: ScopeFilter) -> Optional[List[UUID]]:
    """None => no restriction. Otherwise the entity_ids an Entity query
    should be restricted to (possibly empty => no matches)."""
    if not sf.is_restricted:
        return None
    if sf.scope == "branch_entity":
        return sf.entity_ids
    from app.departments.models.departments import Department
    from app.divisions.models.divisions import Division
    if sf.scope == "department":
        if not sf.department_ids:
            return []
        rows = db.query(Department.entity_id).filter(
            Department.department_id.in_(sf.department_ids)
        ).distinct().all()
        return [r[0] for r in rows]
    if sf.scope == "division":
        if not sf.division_ids:
            return []
        rows = db.query(Division.entity_id).filter(
            Division.id.in_(sf.division_ids)
        ).distinct().all()
        return [r[0] for r in rows]
    return None


def scoped_department_ids(db: Session, sf: ScopeFilter) -> Optional[List[UUID]]:
    """None => no restriction. Otherwise the department_ids a Department
    query should be restricted to."""
    if not sf.is_restricted:
        return None
    if sf.scope == "department":
        return sf.department_ids
    from app.departments.models.departments import Department
    from app.divisions.models.divisions import Division
    if sf.scope == "branch_entity":
        if not sf.entity_ids:
            return []
        rows = db.query(Department.department_id).filter(
            Department.entity_id.in_(sf.entity_ids)
        ).all()
        return [r[0] for r in rows]
    if sf.scope == "division":
        if not sf.division_ids:
            return []
        rows = db.query(Division.department_id).filter(
            Division.id.in_(sf.division_ids), Division.department_id.isnot(None)
        ).distinct().all()
        return [r[0] for r in rows]
    return None


def scoped_division_ids(db: Session, sf: ScopeFilter) -> Optional[List[UUID]]:
    """None => no restriction. Otherwise the division ids (divisions.id) a
    Division query should be restricted to."""
    if not sf.is_restricted:
        return None
    if sf.scope == "division":
        return sf.division_ids
    from app.divisions.models.divisions import Division
    if sf.scope == "branch_entity":
        if not sf.entity_ids:
            return []
        rows = db.query(Division.id).filter(Division.entity_id.in_(sf.entity_ids)).all()
        return [r[0] for r in rows]
    if sf.scope == "department":
        if not sf.department_ids:
            return []
        rows = db.query(Division.id).filter(Division.department_id.in_(sf.department_ids)).all()
        return [r[0] for r in rows]
    return None


def apply_user_scope_filter(query: Query, sf: ScopeFilter) -> Query:
    """Apply array-overlap scope filtering directly to a UserSetupBasic
    query (entity_id/department_id/division_id are all UUID[] columns, so
    this checks for any overlap between the row's array and the acting
    user's assigned IDs, not exact equality)."""
    if not sf.is_restricted:
        return query
    from app.user_setup.models.user_setup import UserSetupBasic
    if sf.scope == "branch_entity":
        return query.filter(UserSetupBasic.entity_id.overlap(sf.entity_ids))
    if sf.scope == "department":
        return query.filter(UserSetupBasic.department_id.overlap(sf.department_ids))
    if sf.scope == "division":
        return query.filter(UserSetupBasic.division_id.overlap(sf.division_ids))
    return query
