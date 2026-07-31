"""
Domain exceptions for the onboarding flow.

These subclass HTTPException so routes can let them propagate untouched, matching
the rest of the service (see app/entities/exceptions.py).
"""
from typing import Optional

from fastapi import HTTPException, status


class MasterUserRequiredError(HTTPException):
    """Onboarding may only be performed by a master-DB user (JWT tenant_id NULL)."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only master platform users can onboard clients",
        )


class DuplicateTenantError(HTTPException):
    """A tenant with the same name or contact email already exists."""

    def __init__(self, detail: str = "Client already exists") -> None:
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class OnboardingUnknownReferenceError(HTTPException):
    """A child record points at a parent UUID that was not supplied in the payload."""

    def __init__(self, what: str, value, parent: str) -> None:
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"{what} references {parent} id {value}, which is not among the "
                f"provided {parent}"
            ),
        )


class OnboardingDuplicateError(HTTPException):
    """The same client-supplied id was provided more than once."""

    def __init__(self, what: str) -> None:
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Duplicate {what} — each must be unique within the request",
        )


class TenantProvisioningError(HTTPException):
    """The tenant row was created but its dedicated database could not be provisioned."""

    def __init__(self, tenant_db_name: Optional[str] = None) -> None:
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Client created but database provisioning failed"
                + (f" for {tenant_db_name}" if tenant_db_name else "")
                + " — run provisioning manually."
            ),
        )


class OnboardingNotFoundError(HTTPException):
    """No onboarded client (tenant) with the given id."""

    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
