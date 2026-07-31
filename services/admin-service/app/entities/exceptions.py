"""
Domain exceptions for entities.

These subclass HTTPException so routes can let them propagate untouched,
matching how the rest of the service surfaces errors (see
app/master_datas/exceptions.py). Status codes and messages preserve the
values previously raised inline by the entity service/routes.
"""
from typing import Optional

from fastapi import HTTPException, status


class EntityNotFoundError(HTTPException):
    """Raised when an entity lookup by id/code finds nothing (or it is deleted)."""

    def __init__(self, identifier: Optional[str] = None):
        detail = "Entity not found" if not identifier else f"Entity '{identifier}' not found"
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class DuplicateEntityCodeError(HTTPException):
    """Raised when creating/updating an entity with an entity_code already in use."""

    def __init__(self, entity_code: Optional[str] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Entity code already registered",
        )
        self.entity_code = entity_code
