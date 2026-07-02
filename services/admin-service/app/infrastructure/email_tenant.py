"""
HTTP client for clan-communication-be email-service.

Call send_account_created_email() after a user is inserted into
usersetup_basic. Failures are always swallowed — an email error must
never roll back or fail the user-creation request.
Use asyncio.create_task(send_account_created_email(...)) for fire-and-forget.
"""
import logging
import uuid
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_account_created_email(
    *,
    to_email: str,
    username: str,
    firstname: Optional[str] = None,
    tenant_id: Optional[str] = None,
    recipient_id: Optional[str] = None,
    temp_password: Optional[str] = None,
) -> None:
    """
    Notify a newly created user that a Clan Module account was created for them.
    Fire-and-forget — never raises.
    """
    display_name = firstname or username or to_email
    subject = "Your Clan Module account has been created"

    password_text = (
        f"\nTemporary password: {temp_password}\n"
        "You will be asked to change it on first login.\n"
        if temp_password else ""
    )
    body_text = (
        f"Hi {display_name},\n\n"
        f"A Clan Module account has been created for you.\n\n"
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
        f"<p>A <b>Clan Module</b> account has been created for you.</p>"
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
                logger.info("[email] account-created email accepted for %s", to_email)
            else:
                logger.warning(
                    "[email] account-created email rejected for %s: %s %s",
                    to_email, resp.status_code, resp.text[:200],
                )
    except Exception as exc:
        logger.error("[email] account-created email failed for %s: %s", to_email, exc)
