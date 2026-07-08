"""
HTTP client for clan-communication-be email-service.

Call send_tenant_invitation_email() after a tenant is created and its
admin user is seeded into usersetup_basic. The email invites the tenant
to the platform with a login link they click to sign in.
Failures are always swallowed — an email error must never roll back or
fail the tenant-creation request.
Use asyncio.create_task(send_tenant_invitation_email(...)) for fire-and-forget.
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
                logger.info("[email] tenant-invitation email accepted for %s", to_email)
            else:
                logger.warning(
                    "[email] tenant-invitation email rejected for %s: %s %s",
                    to_email, resp.status_code, resp.text[:200],
                )
    except Exception as exc:
        logger.error("[email] tenant-invitation email failed for %s: %s", to_email, exc)
