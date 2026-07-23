"""
Domain exceptions for tenants.

These subclass HTTPException so routes can let them propagate untouched,
matching how the rest of the service surfaces errors (see
app/master_datas/exceptions.py). Status codes and messages preserve the
values previously raised inline by the tenant routes.
"""
from typing import Optional

from fastapi import HTTPException, status


class TenantNotFoundError(HTTPException):
    """Raised when a tenant lookup finds nothing."""

    def __init__(self, identifier: Optional[str] = None):
        detail = "Tenant not found" if not identifier else f"Tenant '{identifier}' not found"
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class DuplicateTenantNameError(HTTPException):
    """Raised when creating a tenant with a tenant_name already in use."""

    def __init__(self, name: Optional[str] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant with this name already exists",
        )
        self.name = name


class DuplicateTenantEmailError(HTTPException):
    """Raised when creating a tenant with a contact_email already in use."""

    def __init__(self, email: Optional[str] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant email already exists",
        )
        self.email = email


class InvalidMasterCredentialsError(HTTPException):
    """
    Raised when tenant creation is attempted with an unknown master email or a
    wrong password (same message for both, to avoid user enumeration).
    """

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid master user credentials",
        )


class NotMasterUserError(HTTPException):
    """Raised when a tenant-scoped user attempts to create a tenant."""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only master platform users can create tenants",
        )


class MasterUserInactiveError(HTTPException):
    """Raised when the authorizing master user account is not active."""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Master user account is not active",
        )
