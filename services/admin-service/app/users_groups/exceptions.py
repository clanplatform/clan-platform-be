"""
Domain exceptions for user groups.

These subclass HTTPException so routes can let them propagate untouched,
matching how the rest of the service surfaces errors (see
app/divisions/exceptions.py).
"""
from typing import Optional

from fastapi import HTTPException, status


class UserGroupNotFoundError(HTTPException):
    """Raised when a user group lookup finds nothing."""

    def __init__(self, identifier: Optional[str] = None):
        detail = "User group not found" if not identifier else f"User group '{identifier}' not found"
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class DuplicateUserGroupNameError(HTTPException):
    """Raised when a group_name already exists within the tenant."""

    def __init__(self, name: Optional[str] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User group with this name already exists",
        )
        self.name = name


class DuplicateUserGroupCodeError(HTTPException):
    """Raised when a group_code already exists within the tenant."""

    def __init__(self, group_code: Optional[str] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User group code already exists",
        )
        self.group_code = group_code


class UserGroupTenantNotFoundError(HTTPException):
    """Raised when the tenant a user group is being created under does not exist."""

    def __init__(self, tenant_id: Optional[str] = None):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
        self.tenant_id = tenant_id


class UserGroupRoleNotFoundError(HTTPException):
    """Raised when the default role a user group references does not exist."""

    def __init__(self, role_id: Optional[str] = None):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail="Default role not found")
        self.role_id = role_id


class UserGroupRoleTenantMismatchError(HTTPException):
    """Raised when the default role belongs to a different tenant."""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Default role does not belong to the same tenant",
        )
