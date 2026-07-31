"""Domain exceptions for security settings (subclass HTTPException so routes can
let them propagate untouched, matching the rest of the service)."""
from fastapi import HTTPException, status


class SecurityNotFoundError(HTTPException):
    """Raised when a security-settings lookup by id finds nothing."""

    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail="Security settings not found")
