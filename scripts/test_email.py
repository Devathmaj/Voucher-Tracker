"""Quick one-shot test: send a test email via Resend to devathmaj@gmail.com."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from voucherbot.config.settings import settings
from voucherbot.services.email.sender import send_email

HTML_BODY = """
<div style="font-family:sans-serif;max-width:600px;margin:auto;padding:24px;border:1px solid #e5e7eb;border-radius:8px">
  <h2 style="color:#4f46e5;margin-top:0">VoucherBot &#x2705; Email Module</h2>
  <p>This is a test email confirming that the <strong>Resend</strong> email integration is wired and working correctly.</p>
  <ul>
    <li>Sender service: <code>voucherbot/services/email/sender.py</code></li>
    <li>API: Resend</li>
    <li>Transport: asyncio.to_thread (non-blocking)</li>
  </ul>
  <hr style="border:none;border-top:1px solid #e5e7eb"/>
  <p style="color:#6b7280;font-size:13px">Sent automatically by VoucherBot.</p>
</div>
"""

TEXT_BODY = (
    "VoucherBot - Email Module Test\n\n"
    "This confirms the Resend email integration is wired and working correctly.\n"
    "Service: voucherbot/services/email/sender.py"
)


async def main() -> None:
    recipient = settings.email_id
    if not recipient:
        print("ERROR: EMAIL_ID is not set in your .env file.")
        return

    result = await send_email(
        to=recipient,
        subject="VoucherBot - Email Module Test",
        html=HTML_BODY,
        text=TEXT_BODY,
    )
    if result:
        print(f"SUCCESS - Email sent to {recipient}! Resend ID: {result.get('id')}")
    else:
        print("FAILED - check the log output above for the error.")


if __name__ == "__main__":
    asyncio.run(main())
