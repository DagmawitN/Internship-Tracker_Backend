# core/views/auth_views.py
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth import get_user_model, authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from core.models import UserRole, Student, Department
from django.db import connection
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import UserRole, Student, Company
from core.serializers.auth_serializers import (
    StudentRegistrationSerializer,
    CompanyRegistrationSerializer,
)

User = get_user_model()

# Helper to generate JWT tokens
def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


# -----------------------------
# Student Registration
# -----------------------------

User = get_user_model()

class StudentRegisterView(generics.CreateAPIView):
    serializer_class = StudentRegistrationSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_data = serializer.validated_data.pop('user')
        student_id = serializer.validated_data['student_id']
        department = serializer.validated_data['department']

        # Check eligibility directly in the database
        # Example: using raw SQL, adjust table/column names to match your DB
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) 
                FROM pre_registered_students
                WHERE username = %s AND student_id = %s AND department_id = %s
            """, [user_data['username'], student_id, department.id])
            eligible_count = cursor.fetchone()[0]

        if eligible_count == 0:
            return Response(
                {"error": "You are not eligible for registration."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Create user
        role, _ = UserRole.objects.get_or_create(role_name='STUDENT')
        user = User.objects.create(
            username=user_data['username'],
            email=user_data['email'],
            role=role,
            phone=user_data.get('phone', '')
        )
        user.set_password(user_data['password'])
        user.save()

        # Create student profile
        Student.objects.create(
            user=user,
            department=department,
            student_id=student_id
        )

        refresh = RefreshToken.for_user(user)

        return Response({
            'message': 'Student registered successfully',
            'user_id': user.id,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)
# -----------------------------
# Company Registration
# -----------------------------
class CompanyRegisterView(generics.CreateAPIView):
    serializer_class = CompanyRegistrationSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_data = serializer.validated_data.pop('user')
        # create user for company login
        role, _ = UserRole.objects.get_or_create(role_name='COMPANY')
        user = User.objects.create(
            username=user_data['username'],
            email=user_data['email'],
            role=role,
            first_name=user_data.get('first_name', ''),
            last_name=user_data.get('last_name', ''),
            phone=user_data.get('phone', '')
        )
        user.set_password(user_data['password'])
        user.save()

        # create company record
        company = Company.objects.create(**serializer.validated_data)

        tokens = get_tokens_for_user(user)
        return Response({
            'message': 'Company registered successfully',
            'user_id': user.id,
            'tokens': tokens
        }, status=status.HTTP_201_CREATED)


# -----------------------------
# Login View
# -----------------------------
class LoginView(generics.GenericAPIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        password = request.data.get('password')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.check_password(password):
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

        tokens = get_tokens_for_user(user)
        return Response({
            'user_id': user.id,
            'email': user.email,
            'tokens': tokens
        }, status=status.HTTP_200_OK)


# -----------------------------
# Logout View
# -----------------------------
from rest_framework_simplejwt.tokens import RefreshToken

class LogoutView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response({'error': 'Refresh token is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()  # requires setting up blacklist in settings
            return Response({'message': 'Logged out successfully'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)
