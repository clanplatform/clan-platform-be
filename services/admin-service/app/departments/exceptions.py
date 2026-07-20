"""
Domain exceptions for departments.

These subclass HTTPException so routes can let them propagate untouched,
matching how the rest of the service surfaces errors (see
app/master_datas/exceptions.py and app/entities/exceptions.py). Status codes
and messages preserve the values previously raised inline by the department
service/routes.
"""
from typing import Optional

from fastapi import HTTPException, status


class DepartmentNotFoundError(HTTPException):
    """Raised when a department lookup finds nothing."""

    def __init__(self, identifier: Optional[str] = None):
        detail = "Department not found" if not identifier else f"Department '{identifier}' not found"
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class ParentDepartmentNotFoundError(HTTPException):
    """Raised when the referenced parent department does not exist."""

    def __init__(self):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail="Parent department not found")


class DuplicateDepartmentCodeError(HTTPException):
    """Raised when a department_code already exists within the entity."""

    def __init__(self, department_code: Optional[str] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Department code already exists for this entity",
        )
        self.department_code = department_code


class DepartmentTenantNotFoundError(HTTPException):
    """Raised when the tenant a department is being created under does not exist."""

    def __init__(self, tenant_id: Optional[str] = None):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
        self.tenant_id = tenant_id


class DepartmentEntityNotFoundError(HTTPException):
    """Raised when the entity a department is being created under does not exist."""

    def __init__(self, entity_id: Optional[str] = None):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")
        self.entity_id = entity_id


class EntityTenantMismatchError(HTTPException):
    """Raised when the given entity belongs to a different tenant."""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Entity does not belong to the specified tenant",
        )


class ParentDepartmentMismatchError(HTTPException):
    """Raised when the parent department belongs to a different tenant/entity."""

    def __init__(self, scope: str = "tenant"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Parent department does not belong to the same {scope}",
        )


class DepartmentSelfParentError(HTTPException):
    """Raised when a department is set as its own parent."""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Department cannot be its own parent",
        )


class DepartmentHasChildrenError(HTTPException):
    """Raised when deleting a department that still has active child departments."""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete department with active child departments",
        )


class DepartmentNotDeletedError(HTTPException):
    """Raised when restoring a department that is not soft-deleted."""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Department is not deleted",
        )
