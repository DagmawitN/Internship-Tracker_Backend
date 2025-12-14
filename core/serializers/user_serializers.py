from rest_framework import serializers
from core.models import User,UserRole
from core.permissions import IsAdminUser


class AssignRoleSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    role_name = serializers.CharField(max_length=15)
    def validate_user(self,value):
        try:
            User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User with given ID does not exist.")
        return value
    def validate_role_name(self,value):
        try:
            UserRole.objects.role(role_name=value)
        except UserRole.DoesNotExist:
            raise serializers.ValidationError("Role with given name does not exist.")
        return value

