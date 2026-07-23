"""
Domain exceptions for domains.

These subclass HTTPException so routes can let them propagate untouched,
matching how the rest of the service surfaces errors (see
app/master_datas/exceptions.py, app/entities/exceptions.py and
app/departments/exceptions.py). Messages match what the domains API
returns today (the route-layer wording).
"""
from typing import Optional

from fastapi import HTTPException, status


class DomainNotFoundError(HTTPException):
    """Raised when a domain lookup by id/code/name finds nothing (or it is deleted)."""

    def __init__(self, identifier: Optional[str] = None):
        detail = "Domain not found" if not identifier else f"Domain '{identifier}' not found"
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class DuplicateDomainNameError(HTTPException):
    """Raised when creating/updating a domain with a name already in use."""

    def __init__(self, name: Optional[str] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Domain with this name already exists",
        )
        self.name = name


class DuplicateDomainCodeError(HTTPException):
    """Raised when creating/updating a domain with a code already in use."""

    def __init__(self, code: Optional[str] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Domain with this code already exists",
        )
        self.code = code
