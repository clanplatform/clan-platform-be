"""
Domain exceptions for job codes.

These subclass HTTPException so routes can let them propagate untouched,
matching how the rest of the service surfaces errors (see
app/master_datas/exceptions.py). Status codes and messages preserve the
values previously raised inline by the job code service.
"""
from typing import Optional

from fastapi import HTTPException, status


class JobCodeNotFoundError(HTTPException):
    """
    Raised when a job code lookup finds nothing.

    Pass ``job_code_id`` for by-id lookups or ``code`` for by-code lookups —
    the legacy message wording is preserved for each.
    """

    def __init__(self, job_code_id: Optional[str] = None, code: Optional[str] = None):
        if job_code_id:
            detail = f"Job code with ID {job_code_id} not found"
        elif code:
            detail = f"Job code '{code}' not found"
        else:
            detail = "Job code not found"
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class DuplicateJobCodeError(HTTPException):
    """Raised when creating a job code whose code string already exists."""

    def __init__(self, code: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job code '{code}' already exists",
        )
        self.code = code
