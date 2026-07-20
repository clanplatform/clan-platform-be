"""
Domain exceptions for applications.

These subclass HTTPException so routes can let them propagate untouched,
matching how the rest of the service surfaces errors (see
app/master_datas/exceptions.py). Messages match what the applications API
returns today.
"""
from typing import Optional

from fastapi import HTTPException, status


class ApplicationNotFoundError(HTTPException):
    """Raised when an application lookup finds nothing."""

    def __init__(self, identifier: Optional[str] = None):
        detail = "Application not found" if not identifier else f"Application with id {identifier} not found"
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class DuplicateApplicationNameError(HTTPException):
    """Raised when creating/updating an application with a name already used in the domain."""

    def __init__(self, name: Optional[str] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Application with this name already exists in the domain",
        )
        self.name = name


class ApplicationReadOnlyError(HTTPException):
    """
    Raised when a write is attempted against a read-only application
    (access grants no "write").

    - With ``resource`` (e.g. "modules", "menus"): blocks writes to the
      application's child resources.
    - Without: blocks edits to the application record itself (only an
      'access' change can unlock it).
    """

    def __init__(self, resource: Optional[str] = None):
        if resource:
            detail = f"Application is read-only; cannot create, modify, or delete {resource}."
        else:
            detail = "Application is read-only; include an 'access' change to modify it."
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
