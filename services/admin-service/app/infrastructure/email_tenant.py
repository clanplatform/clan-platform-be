"""
HTTP client for clan-communication-be email-service.

Three emails, all fire-and-forget (asyncio.create_task(...)) after a tenant
is created and its users are seeded:
  - send_tenant_invitation_email() — the owner (owner_email), with their
    temp login password.
  - send_tenant_contact_notification() — the client's general contact
    address (contact_email), only when it differs from owner_email; no
    credentials, since contact_email isn't necessarily a login identity.
  - send_user_invite_email() — any users[] entry with send_invite_email
    true; no password (the user chose their own), just a login link.
Failures are always swallowed — an email error must never roll back or
fail the tenant-creation request.
"""
import logging
import uuid
from typing import Optional
from urllib.parse import quote

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


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


async def send_tenant_contact_notification(
    *,
    to_email: str,
    tenant_name: str,
    tenant_id: str,
    owner_email: str,
) -> None:
    """
    Notify a client's general contact address that onboarding completed,
    without login credentials (contact_email isn't necessarily a login
    identity — only owner_email is seeded as the actual admin user). Only
    call this when contact_email differs from owner_email, to avoid sending
    two emails to the same inbox.
    Fire-and-forget — never raises.
    """
    subject = f"{tenant_name} is now set up on Clan"
    body_text = (
        f"Hello,\n\n"
        f"Your organization, {tenant_name}, has been successfully onboarded "
        "to Clan.\n\n"
        f"The account admin login is: {owner_email}\n"
        "That admin received a separate email with login credentials.\n\n"
        "If you did not request this, please contact the Clan support team "
        "immediately.\n\n"
        "Thank you,\n\n"
        "Team Clan\n"
        "clan.platform@gmail.com\n"
        f"{settings.COMPANY_WEBSITE}"
    )
    body_html = (
        "<p>Hello,</p>"
        f"<p>Your organization, <strong>{tenant_name}</strong>, has been "
        "successfully onboarded to Clan.</p>"
        f"<p>The account admin login is: <strong>{owner_email}</strong><br>"
        "That admin received a separate email with login credentials.</p>"
        "<p>If you did not request this, please contact the Clan support "
        "team immediately.</p>"
        "<p>Thank you,</p>"
        "<p><strong>Team Clan</strong><br>"
        "<a href=\"mailto:clan.platform@gmail.com\">clan.platform@gmail.com</a><br>"
        f"<a href=\"{settings.COMPANY_WEBSITE}\">{settings.COMPANY_WEBSITE}</a></p>"
    )
    await _post_email(
        to_email=to_email,
        tenant_id=tenant_id,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        log_label="tenant-contact-notification",
    )


async def send_user_invite_email(
    *,
    to_email: str,
    first_name: Optional[str],
    tenant_name: str,
    tenant_id: str,
    tenant_app_url: Optional[str] = None,
) -> None:
    """
    Invite a user added during onboarding (users[] with send_invite_email
    true) to log in. Unlike the owner's temp-password email, the user chose
    their own password when the form was submitted, so it isn't repeated
    here — just a login link.
    Fire-and-forget — never raises.
    """
    subject = f"You've been added to {tenant_name} on Clan"
    login_base = (tenant_app_url.rstrip("/") + "/login") if tenant_app_url else settings.FRONTEND_LOGIN_URL
    login_url = f"{login_base}?email={quote(to_email)}&tenant_id={quote(tenant_id)}"
    greeting = f"Hello {first_name}," if first_name else "Hello,"

    body_text = (
        f"{greeting}\n\n"
        f"You've been added as a user of {tenant_name} on Clan. Use the "
        f"email and password set for you to log in:\n\n"
        f"Email: {to_email}\n"
        f"Login URL: {login_url}\n\n"
        "If you did not expect this invitation, please contact the Clan "
        "support team immediately.\n\n"
        "Thank you,\n\n"
        "Team Clan\n"
        "clan.platform@gmail.com\n"
        f"{settings.COMPANY_WEBSITE}"
    )
    body_html = (
        f"<p>{greeting}</p>"
        f"<p>You've been added as a user of <strong>{tenant_name}</strong> "
        "on Clan. Use the email and password set for you to log in:</p>"
        f"<p><strong>Email:</strong> {to_email}</p>"
        f"<p><a href=\"{login_url}\" "
        "style=\"display:inline-block;padding:10px 24px;background:#2563eb;"
        "color:#ffffff;text-decoration:none;border-radius:6px;\">Log In</a></p>"
        f"<p><strong>Login URL:</strong> <a href=\"{login_url}\">{login_url}</a></p>"
        "<p>If you did not expect this invitation, please contact the Clan "
        "support team immediately.</p>"
        "<p>Thank you,</p>"
        "<p><strong>Team Clan</strong><br>"
        "<a href=\"mailto:clan.platform@gmail.com\">clan.platform@gmail.com</a><br>"
        f"<a href=\"{settings.COMPANY_WEBSITE}\">{settings.COMPANY_WEBSITE}</a></p>"
    )
    await _post_email(
        to_email=to_email,
        tenant_id=tenant_id,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        log_label="user-invitation",
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
) -> None:
    """Shared HTTP call to the email-service /send endpoint. Never raises."""
    try:
        # Must exceed the email-service's own SMTP timeout (15s) plus its
        # SendGrid fallback — the /send endpoint blocks until delivery, and a
        # Gmail SMTP handshake alone takes ~5s. A shorter timeout here reports
        # a false failure even when the email was actually sent.
        async with httpx.AsyncClient(timeout=30.0) as http:
            resp = await http.post(
                f"{settings.EMAIL_SERVICE_URL}/api/v1/send",
                json={
                    "notification_id": str(uuid.uuid4()),
                    "tenant_id": tenant_id or "master",
                    "recipient_id": recipient_id or str(uuid.uuid4()),
                    "to_email": to_email,
                    "subject": subject,
                    "body_text": body_text,
                    "body_html": body_html,
                },
            )
            if resp.status_code in (200, 201, 202):
                logger.info("[email] %s email accepted for %s", log_label, to_email)
            else:
                logger.warning(
                    "[email] %s email rejected for %s: %s %s",
                    log_label, to_email, resp.status_code, resp.text[:200],
                )
    except Exception as exc:
        logger.error("[email] %s email failed for %s: %s", log_label, to_email, exc)
