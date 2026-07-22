"""
Email sender service using the Resend API.
"""

from voucherbot.services.email.notifications import notify_voucher_found
from voucherbot.services.email.sender import send_email

__all__ = ["send_email", "notify_voucher_found"]
