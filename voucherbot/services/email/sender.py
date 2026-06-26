"""
Email sender service using the Resend API.

Usage:
    from voucherbot.services.email.sender import send_email

    await send_email(
        to="user@example.com",
        subject="New Voucher Found!",
        html="<p>We found a voucher for you.</p>",
    )
"""
import asyncio
import time
import structlog
from typing import Optional

from voucherbot.config.settings import settings

logger = structlog.get_logger(__name__)

_initialized = False
_send_lock = asyncio.Lock()
_last_send_at = 0.0


def _init() -> None:
    global _initialized
    if not settings.resend_api_key:
        logger.warning("email.sender: RESEND_API_KEY not set - email will be skipped.")
        return
    import resend
    resend.api_key = settings.resend_api_key
    _initialized = True
    logger.info("email.sender: Resend client initialized.")


_init()


async def send_email(
    to: str | list[str],
    subject: str,
    html: str,
    text: Optional[str] = None,
) -> dict | None:
    """
    Send an email via Resend.

    Args:
        to:      Recipient address(es).
        subject: Email subject line.
        html:    HTML body.
        text:    Optional plain-text fallback body.

    Returns:
        The Resend API response dict (contains 'id') or None on failure.
    """
    if not _initialized:
        logger.warning("email.sender: skipping send - not initialized.")
        return None

    import resend

    params: resend.Emails.SendParams = {
        "from": settings.email_from,
        "to": [to] if isinstance(to, str) else to,
        "subject": subject,
        "html": html,
    }
    if text:
        params["text"] = text

    try:
        async with _send_lock:
            global _last_send_at
            elapsed = time.monotonic() - _last_send_at
            delay = settings.email_min_interval_seconds - elapsed
            if delay > 0:
                logger.info(
                    "email.sender: throttling",
                    delay_seconds=round(delay, 2),
                    to=to,
                )
                await asyncio.sleep(delay)

            def _send() -> dict:
                return resend.Emails.send(params)

            result = await asyncio.to_thread(_send)
            _last_send_at = time.monotonic()
        logger.info("email.sender: sent", to=to, subject=subject, id=result.get("id"))
        return result

    except Exception as exc:
        logger.error("email.sender: failed to send", to=to, subject=subject, error=str(exc))
        return None
