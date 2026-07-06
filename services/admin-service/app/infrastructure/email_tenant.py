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
) -> None:
    """
    Invite a newly onboarded tenant to Clan Module. The email contains a
    login link the tenant clicks to accept the invitation and sign in.
    Fire-and-forget — never raises.
    """
    display_name = tenant_name or to_email
    subject = "You're invited to Clan Module"
    # tenant_id in the link lets the login page authenticate against the
    # tenant DB and land the user in the tenant's assigned application.
    login_url = f"{settings.FRONTEND_LOGIN_URL}?email={quote(to_email)}"
    if tenant_id:
        login_url += f"&tenant_id={quote(tenant_id)}"

    password_text = (
        f"Temporary password: {temp_password}\n"
        "You will be asked to change it on first login.\n"
        if temp_password else ""
    )
    body_text = (
        f"Hi {display_name},\n\n"
        "You have been invited to Clan Module.\n\n"
        "Click the link below to accept the invitation and log in:\n"
        f"{login_url}\n\n"
        f"Login email: {to_email}\n"
        f"{password_text}\n"
        "Regards,\nClan Platform"
    )

    password_html = (
        f"<p>Temporary password: <b>{temp_password}</b><br>"
        "You will be asked to change it on first login.</p>"
        if temp_password else ""
    )
    body_html = (
        f"<p>Hi {display_name},</p>"
        f"<p>You have been invited to <b>Clan Module</b>.</p>"
        f"<p><a href=\"{login_url}\" "
        "style=\"display:inline-block;padding:10px 24px;background:#2563eb;"
        "color:#ffffff;text-decoration:none;border-radius:6px;\">"
        "Accept Invitation &amp; Login</a></p>"
        f"<p>Or copy this link into your browser:<br>{login_url}</p>"
        f"<p>Login email: <b>{to_email}</b></p>"
        f"{password_html}"
        f"<p>Regards,<br>Clan Platform</p>"
    )

    try:
        async with httpx.AsyncClient(timeout=5.0) as http:
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
