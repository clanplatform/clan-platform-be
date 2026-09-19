"""
HTTP client for clan-communication-be email-service.

Fire-and-forget (asyncio.create_task(...)) after a tenant is created and its
users are seeded:
  - send_tenant_invitation_email() — the owner (owner_email), with their
    temp login password.
  - send_user_invitation_email() — each onboarding users[] entry whose
    send_invite_email flag is set, with that user's own temp login password.
contact_email is stored for reference only and is never emailed.
Failures are always swallowed — an email error must never roll back or
fail the tenant-creation request.
"""
import asyncio
import logging
import uuid
from typing import Optional
from urllib.parse import quote

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Render's free/starter tier fronts services with Cloudflare, which can
# transiently 429 (rate limit) or 503 (still cold-starting) a request even
# after it reaches the edge - worth a short retry rather than silently
# dropping the email. Network-level failures (timeout, connection refused)
# are equally transient on a cold-starting service and get the same treatment.
_RETRYABLE_STATUS_CODES = {429, 502, 503, 504}
_RETRY_DELAYS_SECONDS = [3.0, 8.0]  # before attempt 2 and attempt 3


async def send_tenant_invitation_email(
    *,
    to_email: str,
    tenant_name: Optional[str] = None,
    tenant_id: Optional[str] = None,
    recipient_id: Optional[str] = None,
    temp_password: Optional[str] = None,
    tenant_app_url: Optional[str] = None,
) -> None:
    """
    Send a newly onboarded tenant their welcome email with temporary login
    credentials (login email + temp password) and a login link. The tenant is
    asked to change the temp password on first login.
    Fire-and-forget — never raises.
    """
    subject = "Welcome to Clan — Your Login Credentials"
    # Prefer the tenant's own frontend (tenants.allowed_origins[0], passed in as
    # tenant_app_url) so the login link points at the tenant's domain; fall back
    # to the platform login page. tenant_id in the query lets the login page
    # authenticate against the tenant DB and land the user in the tenant's app.
    if tenant_app_url:
        login_base = tenant_app_url.rstrip("/") + "/login"
    else:
        login_base = settings.FRONTEND_LOGIN_URL
    login_url = f"{login_base}?email={quote(to_email)}"
    if tenant_id:
        login_url += f"&tenant_id={quote(tenant_id)}"

    website = settings.COMPANY_WEBSITE
    greeting = f"Hello {tenant_name}," if tenant_name else "Hello,"

    body_text = (
        f"{greeting}\n\n"
        "Welcome to Clan!\n\n"
        "Your account has been created successfully. Please use the temporary "
        "login credentials below to log in:\n\n"
        f"Email: {to_email}\n"
        f"Temporary Password: {temp_password}\n\n"
        f"Login URL: {login_url}\n\n"
        "For your security, please change your temporary password immediately "
        "after your first login.\n\n"
        "If you did not request this account or believe you received this email "
        "by mistake, please contact the Clan support team immediately.\n\n"
        "Thank you,\n\n"
        "Team Clan\n"
        "clan.platform@gmail.com\n"
        f"{website}"
    )

    body_html = (
        f"<p>{greeting}</p>"
        "<p>Welcome to <strong>Clan</strong>!</p>"
        "<p>Your account has been created successfully. Please use the "
        "temporary login credentials below to log in:</p>"
        f"<p><strong>Email:</strong> {to_email}<br>"
        f"<strong>Temporary Password:</strong> {temp_password}</p>"
        f"<p><a href=\"{login_url}\" "
        "style=\"display:inline-block;padding:10px 24px;background:#2563eb;"
        "color:#ffffff;text-decoration:none;border-radius:6px;\">Log In</a></p>"
        f"<p><strong>Login URL:</strong> <a href=\"{login_url}\">{login_url}</a></p>"
        "<p>For your security, please change your temporary password "
        "immediately after your first login.</p>"
        "<p>If you did not request this account or believe you received this "
        "email by mistake, please contact the Clan support team immediately.</p>"
        "<p>Thank you,</p>"
        "<p><strong>Team Clan</strong><br>"
        "<a href=\"mailto:clan.platform@gmail.com\">clan.platform@gmail.com</a><br>"
        f"<a href=\"{website}\">{website}</a></p>"
    )

    await _post_email(
        to_email=to_email,
        tenant_id=tenant_id,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        recipient_id=recipient_id,
        log_label="tenant-invitation",
    )


async def send_user_invitation_email(
    *,
    to_email: str,
    first_name: Optional[str] = None,
    tenant_name: Optional[str] = None,
    tenant_id: Optional[str] = None,
    recipient_id: Optional[str] = None,
    temp_password: Optional[str] = None,
    tenant_app_url: Optional[str] = None,
) -> None:
    """
    Send an onboarded end user (a users[] entry with send_invite_email set)
    their welcome email with temporary login credentials (login email + temp
    password) and a login link. Same shape as send_tenant_invitation_email,
    worded for a member of the tenant rather than its owner. The user is asked
    to change the temp password on first login (usersetup_basic
    .can_change_password is True, is_password_change False — see
    onboarding/services/onboarding._create_user_row).
    Fire-and-forget — never raises.
    """
    org = tenant_name or "your organization"
    subject = f"Welcome to Clan — Your {org} Login Credentials" if tenant_name else "Welcome to Clan — Your Login Credentials"

    # Prefer the tenant's own frontend (tenants.deployed_url, passed in as
    # tenant_app_url) so the login link points at the tenant's domain; fall
    # back to the platform login page. tenant_id in the query lets the login
    # page authenticate against the tenant DB.
    if tenant_app_url:
        login_base = tenant_app_url.rstrip("/") + "/login"
    else:
        login_base = settings.FRONTEND_LOGIN_URL
    login_url = f"{login_base}?email={quote(to_email)}"
    if tenant_id:
        login_url += f"&tenant_id={quote(tenant_id)}"

    website = settings.COMPANY_WEBSITE
    greeting = f"Hello {first_name}," if first_name else "Hello,"

    body_text = (
        f"{greeting}\n\n"
        f"An account has been created for you on Clan for {org}.\n\n"
        "Please use the temporary login credentials below to log in:\n\n"
        f"Email: {to_email}\n"
        f"Temporary Password: {temp_password}\n\n"
        f"Login URL: {login_url}\n\n"
        "For your security, please change your temporary password immediately "
        "after your first login.\n\n"
        "If you did not expect this account or believe you received this email "
        "by mistake, please contact your administrator.\n\n"
        "Thank you,\n\n"
        "Team Clan\n"
        "clan.platform@gmail.com\n"
        f"{website}"
    )

    body_html = (
        f"<p>{greeting}</p>"
        f"<p>An account has been created for you on <strong>Clan</strong> for {org}.</p>"
        "<p>Please use the temporary login credentials below to log in:</p>"
        f"<p><strong>Email:</strong> {to_email}<br>"
        f"<strong>Temporary Password:</strong> {temp_password}</p>"
        f"<p><a href=\"{login_url}\" "
        "style=\"display:inline-block;padding:10px 24px;background:#2563eb;"
        "color:#ffffff;text-decoration:none;border-radius:6px;\">Log In</a></p>"
        f"<p><strong>Login URL:</strong> <a href=\"{login_url}\">{login_url}</a></p>"
        "<p>For your security, please change your temporary password "
        "immediately after your first login.</p>"
        "<p>If you did not expect this account or believe you received this "
        "email by mistake, please contact your administrator.</p>"
        "<p>Thank you,</p>"
        "<p><strong>Team Clan</strong><br>"
        "<a href=\"mailto:clan.platform@gmail.com\">clan.platform@gmail.com</a><br>"
        f"<a href=\"{website}\">{website}</a></p>"
    )

    await _post_email(
        to_email=to_email,
        tenant_id=tenant_id,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        recipient_id=recipient_id,
        log_label="user-invitation",
    )


async def send_setup_invitation_email(
    *,
    to_email: str,
    token: str,
    first_name: Optional[str] = None,
    tenant_name: Optional[str] = None,
    tenant_id: Optional[str] = None,
    recipient_id: Optional[str] = None,
    tenant_app_url: Optional[str] = None,
    expires_at: Optional[str] = None,
    temp_password: Optional[str] = None,
) -> bool:
    """
    Send a user_setup user an invitation email. Carries both:
      - an accept-invitation link with an opaque token (never a raw user id —
        see app.core.security.generate_invitation_token); and
      - when temp_password is given, that user's email + a freshly generated
        temporary login password (usersetup_basic.password_hash is
        regenerated to match — see
        UserInvitationService._apply_temp_password), for logging in directly
        without going through the accept-invitation link.
    Never raises. Returns True once the email-service accepts the email, so
    callers can mark user_invitations.status as 'sent' vs 'failed' accurately
    (see app.user_invitations.services.user_invitations).
    """
    org = tenant_name or "your organization"
    subject = f"You're invited to Clan — {org}" if tenant_name else "You're invited to Clan"

    # Prefer the tenant's own frontend (tenants.deployed_url, passed in as
    # tenant_app_url), same precedence as send_user_invitation_email's login
    # link. FRONTEND_LOGIN_URL is ".../login" — swap the last path segment
    # for the accept-invitation page rather than assuming a fixed base.
    if tenant_app_url:
        accept_base = tenant_app_url.rstrip("/") + "/accept-invitation"
        login_base = tenant_app_url.rstrip("/") + "/login"
    else:
        accept_base = settings.FRONTEND_LOGIN_URL.rsplit("/", 1)[0] + "/accept-invitation"
        login_base = settings.FRONTEND_LOGIN_URL
    accept_url = f"{accept_base}?token={quote(token)}"
    login_url = f"{login_base}?email={quote(to_email)}"
    if tenant_id:
        login_url += f"&tenant_id={quote(tenant_id)}"

    website = settings.COMPANY_WEBSITE
    greeting = f"Hello {first_name}," if first_name else "Hello,"
    expiry_line = f" This invitation expires on {expires_at}." if expires_at else ""

    credentials_text = (
        f"You can also log in directly with:\n\n"
        f"Email: {to_email}\n"
        f"Temporary Password: {temp_password}\n\n"
        f"Login URL: {login_url}\n\n"
        "For your security, please change your temporary password immediately "
        "after your first login.\n\n"
    ) if temp_password else ""

    credentials_html = (
        "<p>You can also log in directly with:</p>"
        f"<p><strong>Email:</strong> {to_email}<br>"
        f"<strong>Temporary Password:</strong> {temp_password}</p>"
        f"<p><strong>Login URL:</strong> <a href=\"{login_url}\">{login_url}</a></p>"
        "<p>For your security, please change your temporary password "
        "immediately after your first login.</p>"
    ) if temp_password else ""

    body_text = (
        f"{greeting}\n\n"
        f"You've been invited to join {org} on Clan.\n\n"
        f"Accept your invitation here:\n{accept_url}\n\n"
        f"This link is unique to you — please don't share it.{expiry_line}\n\n"
        f"{credentials_text}"
        "If you did not expect this invitation or believe you received this "
        "email by mistake, please contact your administrator.\n\n"
        "Thank you,\n\n"
        "Team Clan\n"
        "clan.platform@gmail.com\n"
        f"{website}"
    )

    body_html = (
        f"<p>{greeting}</p>"
        f"<p>You've been invited to join <strong>{org}</strong> on Clan.</p>"
        f"<p><a href=\"{accept_url}\" "
        "style=\"display:inline-block;padding:10px 24px;background:#2563eb;"
        "color:#ffffff;text-decoration:none;border-radius:6px;\">Accept Invitation</a></p>"
        f"<p><strong>Invitation link:</strong> <a href=\"{accept_url}\">{accept_url}</a></p>"
        f"<p>This link is unique to you — please don't share it.{expiry_line}</p>"
        f"{credentials_html}"
        "<p>If you did not expect this invitation or believe you received this "
        "email by mistake, please contact your administrator.</p>"
        "<p>Thank you,</p>"
        "<p><strong>Team Clan</strong><br>"
        "<a href=\"mailto:clan.platform@gmail.com\">clan.platform@gmail.com</a><br>"
        f"<a href=\"{website}\">{website}</a></p>"
    )

    return await _post_email(
        to_email=to_email,
        tenant_id=tenant_id,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        recipient_id=recipient_id,
        log_label="setup-invitation",
    )


async def _post_email(
    *,
    to_email: str,
    tenant_id: Optional[str],
    subject: str,
    body_text: str,
    body_html: str,
    recipient_id: Optional[str] = None,
    log_label: str,
) -> bool:
    """Shared HTTP call to the email-service /send endpoint. Never raises.

    Retries up to 3 attempts total on a retryable HTTP status (429/502/503/504)
    or a network-level failure (timeout, connection refused) - both are
    transient on a Render free/starter-tier service that may be cold-starting
    or briefly rate-limited at the edge. This call is fire-and-forget, so the
    extra wait never blocks the caller's actual response.

    Returns True once the email-service accepts the email (2xx), False on any
    rejection/failure/exhausted-retries. Existing callers that don't need
    this (fire-and-forget, no status tracking) can simply ignore it — added
    for callers that DO track delivery status (see
    app.user_invitations.services.user_invitations).
    """
    payload = {
        "notification_id": str(uuid.uuid4()),
        "tenant_id": tenant_id or "master",
        "recipient_id": recipient_id or str(uuid.uuid4()),
        "to_email": to_email,
        "subject": subject,
        "body_text": body_text,
        "body_html": body_html,
    }
    max_attempts = len(_RETRY_DELAYS_SECONDS) + 1

    for attempt in range(1, max_attempts + 1):
        try:
            # Must exceed the email-service's own SMTP timeout (15s) plus its
            # SendGrid fallback — the /send endpoint blocks until delivery, and a
            # Gmail SMTP handshake alone takes ~5s. Also must tolerate a Render
            # free/starter-tier cold start (the service sleeps after inactivity
            # and can take 30-60s to wake on the next request) — a shorter
            # timeout here reports a false failure (and silently drops the
            # email, since this call is fire-and-forget) even when the service
            # would have responded successfully given more time.
            async with httpx.AsyncClient(timeout=90.0) as http:
                resp = await http.post(
                    f"{settings.EMAIL_SERVICE_URL}/api/v1/send",
                    json=payload,
                )
            if resp.status_code in (200, 201, 202):
                logger.info("[email] %s email accepted for %s (attempt %d/%d)", log_label, to_email, attempt, max_attempts)
                return True
            if resp.status_code in _RETRYABLE_STATUS_CODES and attempt < max_attempts:
                delay = _RETRY_DELAYS_SECONDS[attempt - 1]
                logger.warning(
                    "[email] %s email got %s for %s (attempt %d/%d), retrying in %.0fs",
                    log_label, resp.status_code, to_email, attempt, max_attempts, delay,
                )
                await asyncio.sleep(delay)
                continue
            logger.warning(
                "[email] %s email rejected for %s: %s %s",
                log_label, to_email, resp.status_code, resp.text[:200],
            )
            return False
        except httpx.TransportError as exc:
            # Network-level failure (timeout, connection refused, DNS, ...) —
            # same transient causes as a 429/503, worth the same retry.
            if attempt < max_attempts:
                delay = _RETRY_DELAYS_SECONDS[attempt - 1]
                logger.warning(
                    "[email] %s email attempt %d/%d failed for %s: %s, retrying in %.0fs",
                    log_label, attempt, max_attempts, to_email, exc, delay,
                )
                await asyncio.sleep(delay)
                continue
            logger.error("[email] %s email failed for %s: %s", log_label, to_email, exc)
            return False
        except Exception as exc:
            # Unexpected (not a transport issue) — give up immediately, a
            # bug won't fix itself on retry.
            logger.error("[email] %s email failed for %s: %s", log_label, to_email, exc)
            return False
    return False
