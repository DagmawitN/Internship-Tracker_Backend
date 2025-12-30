from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from core.models import UserRole
from core.permissions import IsAdminUser,IsCoordinatorUser,IsStudentUser
from core.serializers.user_serializers import AssignRoleSerializer

User = get_user_model()
class UserViewSet (viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(
        detail = False,
        methods = ['POST'],
        permission_classes = [IsAdminUser],
        url_name = "admin_assign_role",
    )
    def admin_assign_role(self,request):
        serializer = AssignRoleSerializer(date = request.data)
        if not serializer.is_valid():
            return Response(serializer.errors,status = status.HTTP_400_BAD_REQUEST)

        user_id = serializer.validated_data["user_id"]
        role_name = serializer.validated_data["role_name"]

        user = User.objects.get(id = user_id)
        role = UserRole.objects.get(role_name = role_name)
        
        user.role = role
        user.save()
        return Response(
            {
                "message": f"User '{user.username}' assigned as '{role_name}'",
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "role": role_name
            },
            status=status.HTTP_200_OK
        )
    
    @action(
        detail = False,
        methods = ['POST'],
        permission_classes = [IsCoordinatorUser],
        url_name = "coordinator_assign_role",
    )
    def coordinator_assign_role(self,request):
        serializer = AssignRoleSerializer(data = request.data)
        if not serializer.is_valid():
            return Response(serializer.errors,status = status.HTTP_400_BAD_REQUEST)

        user_id = serializer.validated_data["user_id"]
        role_name = serializer.validated_data["role_name"]
        
        user = User.objects.get(id = user_id)
        role = UserRole.objects.get(role_name = role_name)
        if role.role_name not in ['ADVISOR','EXAMINER']:
            return Response(
                {"error": "Coordinators can not assign that role."},
                status=status.HTTP_403_FORBIDDEN
            )
        user.role = role
        user.save()
        return Response(
            {
                "message": f"User '{user.username}' assigned as '{role_name}'",
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "role": role_name
            },
            status=status.HTTP_200_OK
        )