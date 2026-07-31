"""Domain exceptions for subscriptions (subclass HTTPException so routes can let
them propagate untouched, matching the rest of the service)."""
from fastapi import HTTPException, status


class SubscriptionNotFoundError(HTTPException):
    """Raised when a subscription lookup by id finds nothing."""

    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
