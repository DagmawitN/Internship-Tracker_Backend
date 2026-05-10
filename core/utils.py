import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_otp_email(email, otp):
    if settings.DEBUG:
        logger.warning("DEBUG OTP for %s: %s", email, otp)

    if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
        logger.warning(
            "Email credentials are not configured. OTP for %s is %s",
            email,
            otp,
        )
        return 0

    try:
        return send_mail(
            subject="Your OTP Code",
            message=f"Your OTP is {otp}. It expires in 10 minutes.",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send OTP email to %s. OTP is %s", email, otp)
        return 0


def send_password_reset_email(email, reset_link):
    if settings.DEBUG:
        logger.warning("DEBUG PASSWORD RESET LINK for %s: %s", email, reset_link)

    if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
        logger.warning(
            "Email credentials are not configured. Reset link for %s is %s",
            email,
            reset_link,
        )
        return 0

    try:
        return send_mail(
            subject="Reset Your Password",
            message=f"Click the link below to reset your password:\n\n{reset_link}\n\nThis link will expire shortly.",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send password reset email to %s", email)
        return 0
