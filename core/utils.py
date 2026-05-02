from django.core.mail import send_mail
from django.conf import settings


def send_otp_email(email, otp):
    send_mail(
        subject="Your OTP Code",
        message=f"Your OTP is {otp}. It expires in 10 minutes.",
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", settings.EMAIL_HOST_USER),
        recipient_list=[email],
    )


def send_password_reset_email(email, reset_link):
    send_mail(
        subject="Password Reset Request",
        message=(
            "We received a request to reset your password. "
            f"Use the link below to continue:\n\n{reset_link}\n\n"
            "If you did not request this, you can safely ignore this email."
        ),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", settings.EMAIL_HOST_USER),
        recipient_list=[email],
    )
