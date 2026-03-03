# core/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from core.models import Student, Company, UserRole, Department,CompanyMentor
from django.contrib.auth import authenticate

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'phone',"first_name", "last_name"]

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

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        user = authenticate(email=email, password=password)

        if not user:
            raise serializers.ValidationError("Invalid credentials")
       
        attrs["user"] = user

        return attrs
    

class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()