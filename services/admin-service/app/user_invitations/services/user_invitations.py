"""
Service layer for user_invitations: create/send/list/update/cancel.

Sending is split in two deliberately:
  1. Row creation (generate token, hash it, insert the row) — and
     regenerating the invited user's temp login password on usersetup_basic
     (see _apply_temp_password) — is synchronous — it's just local DB
     writes, always fast regardless of how many users are being invited.
  2. Actual delivery — syncing that password hash to auth-service, then
     the email itself via app.infrastructure.email_tenant
     .send_setup_invitation_email — is an HTTP call to an external
     email-service that can take seconds (and retries up to ~3 attempts /
     tens of seconds on a transient failure). For a SINGLE invitation this
     is awaited directly, so the response accurately reports 'sent' vs
     'failed'. For selected/bulk sends (see send_bulk), it never runs
     inline — it's handed to a background task that works through the list
     with bounded concurrency (BULK_SEND_CONCURRENCY), so the request
     returns immediately and neither auth-service nor the email-service is
     ever hit with hundreds of calls at once.

The invitation email itself carries both the accept-invitation link (opaque
token) and, since usersetup_basic's own email + this regenerated temp
password now go out with it, a direct login path — see
app.infrastructure.email_tenant.send_setup_invitation_email.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import generate_invitation_token, hash_invitation_token, generate_temp_password, get_password_hash
from app.infrastructure.database.session import SessionLocal
from app.infrastructure.email_tenant import send_setup_invitation_email
from app.user_invitations.models.user_invitations import UserInvitation
from app.user_setup.models.user_setup import UserSetupBasic
from app.user_setup.services.auth_service_sync import AuthServiceSync, AuthServiceSyncError

logger = logging.getLogger(__name__)

INVITATION_EXPIRY_DAYS = 7
# How many invitation emails may be in flight to the email-service at once
# during a selected/bulk send. Keeps a large batch from opening hundreds of
# concurrent HTTP connections to (and potentially rate-limiting itself
# against) the email-service — the actual "don't send 1000 emails
# synchronously" safeguard, on top of running the whole batch as a
# background task in the first place.
BULK_SEND_CONCURRENCY = 10

# An invitation in one of these states is still "live" — a new send would
# just duplicate it, so selected/bulk sends skip a user who already has one.
_LIVE_STATUSES = ("pending", "sent")


class UserInvitationService:
    """Service for managing invitation-email rows for user_setup users."""

    @staticmethod
    def resolve_tenant_branding(tenant_id: Optional[UUID]) -> Tuple[Optional[str], Optional[str]]:
        """(tenant_name, deployed_url) for the invitation email's greeting
        and accept-link base — same master-DB lookup pattern used by
        UserSetupService._send_invite_email / onboarding's own invite email.
        (None, None) for a master-DB caller (tenant_id None) or a tenant_id
        that doesn't resolve. Never raises."""
        if tenant_id is None:
            return None, None
        try:
            from app.tenants.models.tenants import Tenant
            master_db = SessionLocal()
            try:
                tenant = master_db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
                if not tenant:
                    return None, None
                return tenant.tenant_name, tenant.deployed_url
            finally:
                master_db.close()
        except Exception:
            logger.exception("[user_invitations] failed to resolve tenant branding for %s", tenant_id)
            return None, None

    # ------------------------------------------------------------------
    # Row-level CRUD
    # ------------------------------------------------------------------

    @staticmethod
    def get_invitation(db: Session, invitation_id: UUID) -> Optional[UserInvitation]:
        return db.query(UserInvitation).filter(UserInvitation.id == invitation_id).first()

    @staticmethod
    def list_invitations(
        db: Session,
        skip: int = 0,
        limit: int = 20,
        user_id: Optional[UUID] = None,
        status_filter: Optional[str] = None,
    ) -> Tuple[List[UserInvitation], int]:
        query = db.query(UserInvitation)
        if user_id is not None:
            query = query.filter(UserInvitation.user_id == user_id)
        if status_filter is not None:
            query = query.filter(UserInvitation.status == status_filter)
        total = query.count()
        rows = query.order_by(UserInvitation.created_at.desc()).offset(skip).limit(limit).all()
        return rows, total

    @staticmethod
    def update_invitation_status(db: Session, invitation_id: UUID, new_status: str) -> Optional[UserInvitation]:
        """PUT /user_invitations/{id} — the only thing an invitation record
        can be edited to after creation is its status (email/token/expiry
        are fixed at send time — see the module docstring)."""
        row = UserInvitationService.get_invitation(db, invitation_id)
        if not row:
            return None
        row.status = new_status
        if new_status == "accepted" and row.accepted_at is None:
            row.accepted_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)
        return row

    @staticmethod
    def cancel_invitation(db: Session, invitation_id: UUID) -> Optional[UserInvitation]:
        """DELETE /user_invitations/{id} — soft: transitions status to
        'cancelled' rather than removing the row (SaaS convention: keep the
        history, don't lose the audit trail of who was invited when)."""
        return UserInvitationService.update_invitation_status(db, invitation_id, "cancelled")

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------

    @staticmethod
    def _get_invitable_user(db: Session, user_id: UUID) -> UserSetupBasic:
        """user_id is user_setup.id (the parent table's own PK — see the
        id-swap fixes elsewhere in this codebase for why FKs/path params
        consistently mean that, not usersetup_basic's PK)."""
        basic = db.query(UserSetupBasic).filter(UserSetupBasic.user_setup_id == user_id).first()
        if not basic:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {user_id} not found")
        return basic

    @staticmethod
    def _apply_temp_password(db: Session, basic: UserSetupBasic) -> str:
        """Generate a fresh temp password and store its hash on `basic` —
        same generate_temp_password/get_password_hash pattern as
        UserSetupService.create_user_setup_with_details — so the credentials
        placed in the invitation email (see send_single/send_bulk) actually
        work to log in. is_password_change/can_change_password are reset so
        the user is forced through the change-password flow on first login.
        Returns the RAW password; only its hash is ever persisted, and only
        here, in memory, long enough to email it and sync it to auth-service."""
        raw_password = generate_temp_password()
        basic.password_hash = get_password_hash(raw_password)
        basic.is_password_change = False
        basic.can_change_password = True
        db.flush()
        return raw_password

    @staticmethod
    async def _sync_password_to_auth_service(basic_id: UUID, password_hash: str) -> None:
        """Best-effort push of a regenerated password hash to the
        identity-domain auth-service, same call/behavior as
        UserSetupService.update_user_setup's sync — never raises, a failure
        here must not block sending the invitation email (the admin-service
        copy of the hash is already correct either way)."""
        if not AuthServiceSync.sync_enabled():
            return
        try:
            await AuthServiceSync.update_auth_user(user_id=basic_id, password_hash=password_hash)
        except AuthServiceSyncError as e:
            logger.error("[user_invitations] failed to sync temp password to auth-service for %s: %s", basic_id, e)
        except Exception:
            logger.exception("[user_invitations] unexpected error syncing temp password to auth-service for %s", basic_id)

    @staticmethod
    def _new_invitation_row(db: Session, user_id: UUID, email: str, tenant_id: Optional[UUID]) -> Tuple[UserInvitation, str]:
        """Insert a fresh invitation row (status='pending') and return it
        along with the RAW token — the only place the raw value ever exists;
        only its hash is persisted (see app.core.security
        .hash_invitation_token)."""
        raw_token = generate_invitation_token()
        row = UserInvitation(
            user_id=user_id,
            tenant_id=tenant_id,
            email=email,
            token_hash=hash_invitation_token(raw_token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=INVITATION_EXPIRY_DAYS),
            status="pending",
        )
        db.add(row)
        db.flush()
        return row, raw_token

    @staticmethod
    async def send_single(
        db: Session,
        user_id: UUID,
        tenant_id: Optional[UUID],
        tenant_name: Optional[str] = None,
        tenant_app_url: Optional[str] = None,
    ) -> UserInvitation:
        """POST /user_invitations/ and POST /user_setup/{user_id}/
        send-invitation. Awaits the actual email send (it's one call), so
        the returned row's status accurately reflects whether it went out.
        Also regenerates the user's temp login password (see
        _apply_temp_password) and syncs it to auth-service before sending,
        so the credentials in the email work immediately."""
        basic = UserInvitationService._get_invitable_user(db, user_id)
        row, raw_token = UserInvitationService._new_invitation_row(db, user_id, basic.email, tenant_id)
        temp_password = UserInvitationService._apply_temp_password(db, basic)
        db.commit()
        db.refresh(row)
        db.refresh(basic)

        await UserInvitationService._sync_password_to_auth_service(basic.id, basic.password_hash)

        sent_ok = await send_setup_invitation_email(
            to_email=basic.email,
            token=raw_token,
            first_name=basic.firstname,
            tenant_name=tenant_name,
            tenant_id=str(tenant_id) if tenant_id else None,
            recipient_id=str(basic.id),
            tenant_app_url=tenant_app_url,
            expires_at=row.expires_at.strftime("%Y-%m-%d"),
            temp_password=temp_password,
        )
        row.status = "sent" if sent_ok else "failed"
        row.sent_at = datetime.now(timezone.utc) if sent_ok else row.sent_at
        db.commit()
        db.refresh(row)
        return row

    @staticmethod
    def _eligible_user_ids(db: Session, user_ids: Optional[List[UUID]] = None) -> Tuple[List[UUID], List[dict]]:
        """Resolve which of `user_ids` (or, when None, every active user in
        this tenant scope — the 'bulk' case) don't already have a live
        (pending/sent, unexpired) invitation. Returns (eligible, skipped)."""
        skipped: List[dict] = []
        now = datetime.now(timezone.utc)

        if user_ids is not None:
            candidates = db.query(UserSetupBasic).filter(UserSetupBasic.user_setup_id.in_(user_ids)).all()
            found_ids = {c.user_setup_id for c in candidates}
            for uid in user_ids:
                if uid not in found_ids:
                    skipped.append({"user_id": uid, "reason": "user not found"})
        else:
            candidates = db.query(UserSetupBasic).filter(UserSetupBasic.status == "active").all()

        eligible_basics = []
        for basic in candidates:
            if user_ids is not None and basic.status != "active":
                skipped.append({"user_id": basic.user_setup_id, "reason": f"user status is '{basic.status}', not active"})
                continue
            live = (
                db.query(UserInvitation)
                .filter(
                    UserInvitation.user_id == basic.user_setup_id,
                    UserInvitation.status.in_(_LIVE_STATUSES),
                    UserInvitation.expires_at > now,
                )
                .first()
            )
            if live:
                skipped.append({"user_id": basic.user_setup_id, "reason": f"already has a live invitation ({live.status})"})
                continue
            eligible_basics.append(basic)

        return eligible_basics, skipped

    @staticmethod
    def create_bulk_rows(
        db: Session,
        tenant_id: Optional[UUID],
        user_ids: Optional[List[UUID]] = None,
    ) -> Tuple[List[Tuple[UserInvitation, str, UserSetupBasic, str]], List[dict]]:
        """Synchronous half of a selected/bulk send: resolve eligibility,
        insert one 'pending' row per eligible user, and regenerate each
        user's temp login password (see _apply_temp_password) — all in the
        caller's own request-scoped `db`/transaction (fast, local writes
        only, regardless of how many users are being invited). Returns
        [(row, raw_token, basic, temp_password), ...] plus the skip list —
        the raw tokens/passwords are only ever available here, in memory,
        for the background task (see send_bulk) to actually sync/email;
        never persisted."""
        eligible_basics, skipped = UserInvitationService._eligible_user_ids(db, user_ids)

        created: List[Tuple[UserInvitation, str, UserSetupBasic, str]] = []
        for basic in eligible_basics:
            row, raw_token = UserInvitationService._new_invitation_row(
                db, basic.user_setup_id, basic.email, tenant_id
            )
            temp_password = UserInvitationService._apply_temp_password(db, basic)
            created.append((row, raw_token, basic, temp_password))

        db.commit()
        for row, _raw_token, basic, _temp_password in created:
            db.refresh(row)
            db.refresh(basic)
        return created, skipped

    @staticmethod
    async def send_bulk(
        invitations: List[Tuple[UUID, str, Optional[str], str]],
        tenant_id: Optional[UUID],
        tenant_name: Optional[str] = None,
        tenant_app_url: Optional[str] = None,
    ) -> None:
        """Background task: actually deliver a batch of already-created
        invitations, at most BULK_SEND_CONCURRENCY at a time — syncing each
        recipient's regenerated temp password (see create_bulk_rows /
        _apply_temp_password) to auth-service, then emailing it, then
        updating that row's status/sent_at as it completes. Takes
        (invitation_id, raw_token, first_name, temp_password) tuples rather
        than ORM rows — this runs after the request's own `db` session has
        been closed, so it opens its own session per recipient (short-lived,
        one per send) to avoid holding one connection open for the whole
        batch's duration.
        """
        semaphore = asyncio.Semaphore(BULK_SEND_CONCURRENCY)

        async def _send_one(invitation_id: UUID, raw_token: str, first_name: Optional[str], temp_password: str) -> None:
            async with semaphore:
                db = SessionLocal()
                try:
                    row = db.query(UserInvitation).filter(UserInvitation.id == invitation_id).first()
                    if not row:
                        return
                    basic = db.query(UserSetupBasic).filter(UserSetupBasic.user_setup_id == row.user_id).first()
                    if basic:
                        await UserInvitationService._sync_password_to_auth_service(basic.id, basic.password_hash)
                    sent_ok = await send_setup_invitation_email(
                        to_email=row.email,
                        token=raw_token,
                        first_name=first_name,
                        tenant_name=tenant_name,
                        tenant_id=str(tenant_id) if tenant_id else None,
                        recipient_id=str(row.user_id),
                        tenant_app_url=tenant_app_url,
                        expires_at=row.expires_at.strftime("%Y-%m-%d"),
                        temp_password=temp_password,
                    )
                    row.status = "sent" if sent_ok else "failed"
                    if sent_ok:
                        row.sent_at = datetime.now(timezone.utc)
                    db.commit()
                except Exception:
                    logger.exception("[user_invitations] background send failed for invitation %s", invitation_id)
                    db.rollback()
                finally:
                    db.close()

        await asyncio.gather(*(
            _send_one(inv_id, token, name, temp_password)
            for inv_id, token, name, temp_password in invitations
        ))
