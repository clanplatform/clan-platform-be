from typing import Optional, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, field_validator

from app.user_invitations.models.user_invitations import INVITATION_STATUSES

INVITATION_STATUS_VALUES = set(INVITATION_STATUSES)


def _validate_status(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    if v not in INVITATION_STATUS_VALUES:
        raise ValueError(f"Invalid status: {v}. Must be one of {sorted(INVITATION_STATUS_VALUES)}")
    return v


# ============================================================================
# Create / Update
# ============================================================================

class UserInvitationCreate(BaseModel):
    """Schema for creating (and sending) a single invitation.

    Used by both POST /user_invitations/ and POST /user_setup/{user_id}/
    send-invitation. tenant_id/email/token_hash/expires_at/status are all
    backend-managed — never accepted here (tenant_id from the JWT, email
    from the user's own usersetup_basic row, token generated server-side)."""
    user_id: UUID = Field(..., description="user_setup.id of the user to invite")

    model_config = ConfigDict(
        json_schema_extra={"example": {"user_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"}}
    )


class UserInvitationBulkCreate(BaseModel):
    """Schema for POST /user_setup/send-invitations — a caller-selected list
    of users to invite in one call."""
    user_ids: List[UUID] = Field(..., min_length=1, description="user_setup.id values to invite")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_ids": [
                    "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "7fb46a5d-462f-4c7e-8430-505d4a1cd050",
                ]
            }
        }
    )


class UserInvitationUpdate(BaseModel):
    """Schema for PUT /user_invitations/{invitation_id} — status transitions
    only. email/token/expiry are set at send time and not directly editable
    (resend by sending a new invitation via /send-invitation instead, which
    creates a fresh row with its own token)."""
    status: Optional[str] = Field(
        None, description=f"One of: {', '.join(sorted(INVITATION_STATUS_VALUES))}"
    )

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        return _validate_status(v)

    model_config = ConfigDict(json_schema_extra={"example": {"status": "cancelled"}})


# ============================================================================
# Response
# ============================================================================

class UserInvitationResponse(BaseModel):
    """Schema for an invitation record.

    token_hash is intentionally never exposed here — the accept flow gets
    the raw token only once, in the email itself (see
    app.core.security.generate_invitation_token / hash_invitation_token)."""
    id: UUID
    user_id: UUID = Field(..., description="user_setup.id — the invited user")
    tenant_id: Optional[UUID] = None
    email: str
    expires_at: datetime
    status: str
    sent_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserInvitationListResponse(BaseModel):
    invitations: List[UserInvitationResponse]
    total: int
    page: int
    size: int
    total_pages: int

    model_config = ConfigDict(from_attributes=True)


class SkippedInvitation(BaseModel):
    """One user_id that a selected/bulk send didn't queue, and why (e.g.
    already has a live pending/sent invitation, or the user wasn't found)."""
    user_id: UUID
    reason: str


class BulkInvitationResult(BaseModel):
    """Response for the selected/bulk send endpoints.

    The user_invitations rows are created synchronously (fast, local DB
    writes only) so `invitation_ids`/`queued` are accurate immediately —
    but the actual email delivery happens in a background task with bounded
    concurrency (see UserInvitationService.send_bulk), so `status` on each
    row starts as 'pending' and only becomes 'sent'/'failed' a short time
    later. Poll GET /user_invitations/?status=... for final delivery state.
    """
    queued: int = Field(..., description="Number of invitations created and queued for sending")
    skipped: List[SkippedInvitation] = Field(default_factory=list)
    invitation_ids: List[UUID] = Field(default_factory=list)
