from rest_framework import serializers

from core.models import Profile, User, UserRole
from core.permissions import IsAdminUser


class AssignRoleSerializer(serializers.Serializer):
    user = serializers.SlugRelatedField(queryset=User.objects.all(), slug_field="email", required=False)
    user_id = serializers.IntegerField(required=False, write_only=True)
    role = serializers.SlugRelatedField(
        queryset=UserRole.objects.all(),
        slug_field="role_name"
    )

    def validate(self, attrs):
        user = attrs.get("user")
        user_id = attrs.get("user_id")

        if user and user_id and user.id != user_id:
            raise serializers.ValidationError({"user_id": "Does not match the provided user."})

        if not user:
            if not user_id:
                raise serializers.ValidationError({"user": "This field is required."})
            try:
                user = User.objects.get(pk=user_id)
            except User.DoesNotExist as exc:
                raise serializers.ValidationError({"user_id": "Invalid user."}) from exc

        attrs["user"] = user
        return attrs

    def save(self):
        user = self.validated_data["user"]
        role = self.validated_data["role"]
        user.role = role
        user.save()
        return user
    
class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = "__all__"