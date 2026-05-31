# core/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from core.models import Student, Company, UserRole, Department,CompanyMentor,PreRegisteredStaff
from django.contrib.auth import authenticate
from .user_serializers import ProfileSerializer


User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    profile = ProfileSerializer(read_only=True)
    department = serializers.SerializerMethodField(read_only=True)
    department_id = serializers.SerializerMethodField(read_only=True)
    department_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'password',
            'phone',
            "profile",
            'department',
            'department_id',
            'department_name',
        ]

    def _resolve_department(self, obj):
        student = getattr(obj, "student_profile", None)
        return getattr(student, "department", None) if student else None

    def get_department(self, obj):
        department = self._resolve_department(obj)
        return department.department_name if department else None

    def get_department_id(self, obj):
        department = self._resolve_department(obj)
        return department.id if department else None

    def get_department_name(self, obj):
        return self.get_department(obj)

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class StudentRegistrationSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    department = serializers.SlugRelatedField(
        queryset=Department.objects.all(),
        slug_field="department_name"
    )

    class Meta:
        model = Student
        fields = ['user', 'student_id', 'department']

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        role, _ = UserRole.objects.get_or_create(role_name='STUDENT')
        user_data['role'] = role
        user = UserSerializer.create(UserSerializer(), validated_data=user_data)
        student = Student.objects.create(user=user, **validated_data)
        return student


class CompanyRegistrationSerializer(serializers.ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = Company
        fields = ['user', 'company_name', 'registration_number', 'industry_type', 'address', 'contact_email', 'contact_phone', 'website']

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        role, _ = UserRole.objects.get_or_create(role_name='COMPANY')
        user_data['role'] = role
        user = UserSerializer.create(UserSerializer(), validated_data=user_data)
        company = Company.objects.create(**validated_data)
        CompanyMentor.objects.create(user=user, company=company)
        return company

class LoginSerializer(serializers.Serializer):
    email = serializers.CharField()
    password = serializers.CharField(write_only=True)
    role = serializers.CharField(required=False, allow_blank=True)  # Selected role from frontend

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")
        selected_role = attrs.get("role", "").strip()

        user = authenticate(email=email, password=password)

        if not user:
            raise serializers.ValidationError("Invalid credentials")
        
        # If a role was selected, verify it matches the user's actual role
        if selected_role:
            # Map role names to match what's stored in the database
            role_map = {
                "Student": "STUDENT",
                "Advisor": "ADVISOR",
                "Coordinator": "COORDINATOR",
                "Examiner": "EXAMINER",
                "Company": "COMPANY",
            }
            
            expected_role = role_map.get(selected_role)
            actual_role = user.role.role_name if user.role else None
            
            if expected_role and expected_role != actual_role:
                raise serializers.ValidationError(
                    f"Invalid credentials for {selected_role} role. Your account is registered as {actual_role}."
                )
       
        attrs["user"] = user

        return attrs
    

class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class StaffRegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        email = attrs.get("email")
        pre_reg = PreRegisteredStaff.objects.filter(email__iexact=email,is_used=False).first()
        if not pre_reg:
            raise serializers.ValidationError("This staff is not pre-registered or already used.")
        # Check for existing user by email
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("A user with that email already exists.")
        # Check for existing username to avoid IntegrityError on create
        username = attrs.get("username")
        if username and User.objects.filter(username__iexact=username).exists():
            raise serializers.ValidationError("This username is already taken. Please choose a different username.")
        attrs['pre_reg'] = pre_reg
        return attrs
    


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)
