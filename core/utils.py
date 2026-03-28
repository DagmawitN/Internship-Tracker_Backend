from django.core.mail import send_mail

def send_otp_email(email, otp):
    send_mail(
        subject="Your OTP Code",
        message=f"Your OTP is {otp}. It expires in 10 minutes.",
        from_email="your_email@gmail.com",
        recipient_list=[email],
    )