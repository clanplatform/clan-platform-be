"""
Domain exceptions for divisions.

These subclass HTTPException so routes can let them propagate untouched,
matching how the rest of the service surfaces errors (see
app/master_datas/exceptions.py and app/departments/exceptions.py). Status
codes and messages preserve the values previously raised inline by the
division service/routes.
"""
from typing import Optional

from fastapi import HTTPException, status


class DivisionNotFoundError(HTTPException):
    """Raised when a division lookup finds nothing."""

    def __init__(self, identifier: Optional[str] = None):
        detail = "Division not found" if not identifier else f"Division '{identifier}' not found"
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class DuplicateDivisionNameError(HTTPException):
    """Raised when a division name already exists within the entity."""

    def __init__(self, name: Optional[str] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Division with this name already exists in this entity",
        )
        self.name = name


class DuplicateDivisionCodeError(HTTPException):
    """Raised when a division_code already exists within the entity."""

    def __init__(self, division_code: Optional[str] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Division code already exists for this entity",
        )
        self.division_code = division_code


class DivisionTenantNotFoundError(HTTPException):
    """Raised when the tenant a division is being created under does not exist."""

    def __init__(self, tenant_id: Optional[str] = None):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
        self.tenant_id = tenant_id


class DivisionEntityNotFoundError(HTTPException):
    """Raised when the entity a division is being created under does not exist."""

    def __init__(self, entity_id: Optional[str] = None):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")
        self.entity_id = entity_id


class DivisionEntityTenantMismatchError(HTTPException):
    """Raised when the given entity belongs to a different tenant."""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Entity does not belong to the specified tenant",
        )


class DivisionDepartmentNotFoundError(HTTPException):
    """Raised when the department a division references does not exist."""

    def __init__(self, department_id: Optional[str] = None):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
        self.department_id = department_id


class DivisionDepartmentTenantMismatchError(HTTPException):
    """
    Raised when the referenced department belongs to a different tenant.
    ``kind`` preserves the legacy wording: "specified" (create) or "same" (update).
    """

    def __init__(self, kind: str = "specified"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Department does not belong to the {kind} tenant",
        )


class DivisionNotDeletedError(HTTPException):
    """Raised when restoring a division that is not soft-deleted."""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Division is not deleted",
        )
