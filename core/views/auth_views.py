# core/views/auth_views.py
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.db import connection, transaction
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import (
    Company,
    CompanyMentor,
    Department,
    EmailOTP,
    PreRegisteredStaff,
    PreRegisteredStudent,
    Profile,
    Staff,
    Student,
    UserRole,
)
from core.serializers.auth_serializers import (
    CompanyRegistrationSerializer,
    LoginSerializer,
    LogoutSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    StaffRegistrationSerializer,
    StudentRegistrationSerializer,
)
from core.utils import send_otp_email, send_password_reset_email

User = get_user_model()


# Helper to generate JWT tokens
def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


# -----------------------------
# Student Registration
# -----------------------------

User = get_user_model()


class StudentRegisterView(generics.CreateAPIView):
    serializer_class = StudentRegistrationSerializer
    permission_classes = [AllowAny]

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_data = serializer.validated_data.pop("user")
        student_id = serializer.validated_data["student_id"]
        department = serializer.validated_data["department"]

        # Verify if PreRegisteredStudent exists
        pre_reg = PreRegisteredStudent.objects.filter(
            student_id=student_id,
            department=department,
            is_used=False,  # Only allow registration once
        ).first()
        if not pre_reg:
            return Response(
                {
                    "error": "You are not eligible for registration or already registered."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        role, _ = UserRole.objects.get_or_create(role_name="STUDENT")
        user = User.objects.create(
            username=user_data["username"],
            email=user_data["email"],
            role=role,
            phone=user_data.get("phone", ""),
        )
        user.set_password(user_data["password"])
        user.save()
        Profile.objects.get_or_create(user=user)
        Student.objects.create(user=user, department=department, student_id=student_id)
        pre_reg.is_used = True
        pre_reg.save()

        if settings.DEBUG:
            # Development: auto-verify, skip OTP, return tokens immediately
            user.is_verified = True
            user.save(update_fields=["is_verified"])
            tokens = get_tokens_for_user(user)
            return Response(
                {
                    "message": "Student registered successfully (dev mode: OTP skipped).",
                    "tokens": tokens,
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "role": user.role.role_name,
                        "student": {
                            "student_id": student_id,
                            "department": department.id,
                        },
                    },
                },
                status=201,
            )

        # Production: send OTP, require verification before login
        otp_code = EmailOTP.generate_otp()
        EmailOTP.objects.create(user=user, otp=otp_code)
        send_otp_email(user.email, otp_code)

        return Response(
            {
                "message": "Student registered successfully. Please verify OTP.",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "role": user.role.role_name,
                    "profile": {
                        "bio": user.profile.bio if hasattr(user, "profile") else "",
                        "avatar": user.profile.avatar.url
                        if hasattr(user, "profile") and user.profile.avatar
                        else None,
                    },
                    "student": {"student_id": student_id, "department": department.id},
                },
            },
            status=201,
        )


# -----------------------------
# Company Registration
# -----------------------------
class CompanyRegisterView(generics.CreateAPIView):
    serializer_class = CompanyRegistrationSerializer
    permission_classes = [AllowAny]

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        company_data = serializer.validated_data

        user_data = company_data.pop("user")
        # create user for company login
        role, _ = UserRole.objects.get_or_create(role_name="COMPANY")
        user = User.objects.create(
            username=user_data["username"],
            email=user_data["email"],
            role=role,
            first_name=user_data.get("first_name", ""),
            last_name=user_data.get("last_name", ""),
            phone=user_data.get("phone", ""),
        )
        user.set_password(user_data["password"])
        user.save()
        Profile.objects.get_or_create(user=user)

        # create company record
        company = Company.objects.create(**company_data)

        CompanyMentor.objects.create(user=user, company=company)

        if settings.DEBUG:
            # Development: auto-verify, skip OTP, return tokens immediately
            user.is_verified = True
            user.save(update_fields=["is_verified"])
            tokens = get_tokens_for_user(user)
            return Response(
                {
                    "message": "Company registered successfully (dev mode: OTP skipped).",
                    "tokens": tokens,
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "role": user.role.role_name,
                        "company_id": company.id,
                    },
                },
                status=201,
            )

        # Production: send OTP, require verification before login
        otp_code = EmailOTP.generate_otp()
        EmailOTP.objects.create(user=user, otp=otp_code)
        send_otp_email(user.email, otp_code)

        return Response(
            {
                "message": "Company registered successfully. Please verify OTP.",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "role": user.role.role_name,
                    "profile": {
                        "bio": user.profile.bio if hasattr(user, "profile") else "",
                        "avatar": user.profile.avatar.url
                        if hasattr(user, "profile") and user.profile.avatar
                        else None,
                    },
                },
            },
            status=201,
        )


# -----------------------------
# Login View
# -----------------------------
class LoginView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]

        # In production, require email verification before login
        if not settings.DEBUG and not user.is_verified:
            return Response(
                {"error": "Email not verified. Please verify OTP."}, status=403
            )

        tokens = get_tokens_for_user(user)

        return Response(
            {
                "user_id": user.id,
                "email": user.email,
                "role": user.role.role_name,
                "tokens": tokens,
            },
            status=status.HTTP_200_OK,
        )


# -----------------------------
# Logout View
# -----------------------------
from rest_framework_simplejwt.tokens import RefreshToken


class LogoutView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LogoutSerializer

    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"error": "Refresh token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()  # requires setting up blacklist in settings
            return Response(
                {"message": "Logged out successfully"}, status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"error": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST
            )


# -----------------------------
# verify otp View
# -----------------------------
from rest_framework import serializers


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField()


class VerifyOTPView(APIView):
    permission_classes = [AllowAny]
    serializer_class = VerifyOTPSerializer

    def post(self, request):
        email = request.data.get("email")
        otp = request.data.get("otp")

        try:
            user = User.objects.get(email=email)
            otp_obj = EmailOTP.objects.filter(user=user, otp=otp).last()

            if not otp_obj:
                return Response({"error": "Invalid OTP"}, status=400)

            if otp_obj.is_expired():
                return Response({"error": "OTP expired"}, status=400)

            user.is_verified = True
            user.save()

            otp_obj.delete()

            tokens = get_tokens_for_user(user)

            return Response(
                {"message": "Email verified successfully", "tokens": tokens}
            )

        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)


class ResendOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")

        try:
            user = User.objects.get(email=email)

            otp_code = EmailOTP.generate_otp()
            EmailOTP.objects.create(user=user, otp=otp_code)

            send_otp_email(user.email, otp_code)

            return Response({"message": "OTP resent successfully"})

        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)


class StaffRegisterView(generics.CreateAPIView):
    serializer_class = StaffRegistrationSerializer
    permission_classes = [AllowAny]

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pre_reg = serializer.validated_data["pre_reg"]

        role_name = "COORDINATOR" if pre_reg.role == "COORDINATOR" else "STAFF"
        role_obj, _ = UserRole.objects.get_or_create(role_name=role_name)

        user = User.objects.create(
            username=serializer.validated_data["username"],
            email=serializer.validated_data["email"],
            role=role_obj,
        )
        user.set_password(serializer.validated_data["password"])
        user.save()
        Profile.objects.get_or_create(user=user)

        Staff.objects.create(
            user=user, department=pre_reg.department, name=pre_reg.name
        )

        pre_reg.is_used = True
        pre_reg.save()

        if settings.DEBUG:
            # Development: auto-verify, skip OTP, return tokens immediately
            user.is_verified = True
            user.save(update_fields=["is_verified"])
            tokens = get_tokens_for_user(user)
            return Response(
                {
                    "message": "Staff registered successfully (dev mode: OTP skipped).",
                    "tokens": tokens,
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "role": user.role.role_name,
                    },
                },
                status=201,
            )

        # Production: send OTP, require verification before login
        otp_code = EmailOTP.generate_otp()
        EmailOTP.objects.create(user=user, otp=otp_code)
        send_otp_email(user.email, otp_code)

        return Response(
            {
                "message": "Staff registered successfully. Please verify OTP.",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "role": user.role.role_name,
                    "profile": {
                        "bio": user.profile.bio if hasattr(user, "profile") else "",
                        "avatar": user.profile.avatar.url
                        if hasattr(user, "profile") and user.profile.avatar
                        else None,
                    },
                },
            },
            status=201,
        )


class PasswordResetRequestView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = PasswordResetRequestSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        user = User.objects.filter(email=email).first()

        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            frontend_base_url = getattr(
                settings,
                "FRONTEND_RESET_PASSWORD_URL",
                "http://localhost:3000/reset-password",
            )
            reset_link = f"{frontend_base_url}?uid={uid}&token={token}"
            send_password_reset_email(user.email, reset_link)

        return Response(
            {
                "message": "If an account with that email exists, a reset link has been sent."
            },
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = PasswordResetConfirmSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uid = serializer.validated_data["uid"]
        token = serializer.validated_data["token"]
        new_password = serializer.validated_data["new_password"]

        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
        except Exception:
            return Response(
                {"error": "Invalid reset link."}, status=status.HTTP_400_BAD_REQUEST
            )

        if not default_token_generator.check_token(user, token):
            return Response(
                {"error": "Invalid or expired token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save()

        return Response(
            {"message": "Password reset successful."}, status=status.HTTP_200_OK
        )
