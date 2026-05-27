from rest_framework import serializers

from core.models import Department, Staff


class StaffSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    role = serializers.CharField(source="user.role.role_name", read_only=True)
    department_name = serializers.CharField(source="department.department_name", read_only=True)

    class Meta:
        model = Staff
        fields = [
            "id",
            "user_id",
            "name",
            "username",
            "email",
            "role",
            "department",
            "department_name",
            "is_assigned",
            "created_at",
        ]
        read_only_fields = fields


class DepartmentQuerySerializer(serializers.Serializer):
    department = serializers.CharField(required=False, allow_blank=True)
