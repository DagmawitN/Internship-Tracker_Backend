from rest_framework import serializers
from core.models import User,UserRole
from core.permissions import IsAdminUser


class AssignRoleSerializer(serializers.Serializer):
    user = serializers.SlugRelatedField(
        queryset=User.objects.all(),
        slug_field="email"
    )
    role = serializers.SlugRelatedField(
        queryset=UserRole.objects.all(),
        slug_field="role_name"
    )

    def save(self):
        user = self.validated_data["user"]
        role = self.validated_data["role"]
        user.role = role
        user.save()
        return user
    
