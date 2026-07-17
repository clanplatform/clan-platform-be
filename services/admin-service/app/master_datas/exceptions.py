"""
Domain exceptions for master data.

These subclass HTTPException so routes can let them propagate untouched,
matching how the rest of the service surfaces errors.
"""
from fastapi import HTTPException, status


class ReferencedByChildrenError(HTTPException):
    """
    Raised by a parent's delete when rows still point at it. Every FK in this
    module is ON DELETE RESTRICT, so without this check psycopg2 would raise
    IntegrityError out of the route as an opaque 500.
    """

    def __init__(self, parent: str, child: str, count: int):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot delete {parent}: {count} {child} still reference it. "
                f"Delete those {child} first, or set is_active=false to retire the {parent}."
            ),
        )


class CountryNotFoundError(HTTPException):
    def __init__(self, identifier: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Country '{identifier}' not found",
        )


class DuplicateCountryError(HTTPException):
    def __init__(self, field: str, value: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A country with {field}='{value}' already exists",
        )


class StateNotFoundError(HTTPException):
    def __init__(self, identifier: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"State '{identifier}' not found",
        )


class DuplicateStateError(HTTPException):
    def __init__(self, field: str, value: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A state with {field}='{value}' already exists for this country",
        )


class CityNotFoundError(HTTPException):
    def __init__(self, identifier: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"City '{identifier}' not found",
        )


class DuplicateCityError(HTTPException):
    def __init__(self, field: str, value: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A city with {field}='{value}' already exists for this state",
        )


class LanguageNotFoundError(HTTPException):
    def __init__(self, identifier: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Language '{identifier}' not found",
        )


class DuplicateLanguageError(HTTPException):
    def __init__(self, field: str, value: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A language with {field}='{value}' already exists",
        )


class LocaleNotFoundError(HTTPException):
    def __init__(self, identifier: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Locale '{identifier}' not found",
        )


class DuplicateLocaleError(HTTPException):
    def __init__(self, field: str, value: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A locale with {field}='{value}' already exists",
        )
