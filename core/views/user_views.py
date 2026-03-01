from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from core.models import UserRole
from core.permissions import IsAdminUser,IsCoordinatorUser,IsStudentUser
from core.serializers.user_serializers import AssignRoleSerializer
from rest_framework import generics
from core.serializers.auth_serializers import UserSerializer

User = get_user_model()

class UserViewSet(viewsets.GenericViewSet):
    queryset = User.objects.all()
    serializer_class = AssignRoleSerializer
    permission_classes = [IsAuthenticated]

    @action(
        detail=False,
        methods=['post'],
        permission_classes=[IsAdminUser],
        url_name="admin_assign_role",
    )
    def admin_assign_role(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        role = serializer.validated_data["role"]

        user.role = role
        user.save()

        return Response(
            {
                "message": f"User '{user.username}' assigned as '{role.role_name}'",
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "role": role.role_name,
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=['post'],
        permission_classes=[IsCoordinatorUser],
        url_name="coordinator_assign_role",
    )
    def coordinator_assign_role(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        role = serializer.validated_data["role"]

        if role.role_name not in ['ADVISOR', 'EXAMINER']:
            return Response(
                {"error": "Coordinators cannot assign that role."},
                status=status.HTTP_403_FORBIDDEN,
            )

        user.role = role
        user.save()

        return Response(
            {
                "message": f"User '{user.username}' assigned as '{role.role_name}'",
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "role": role.role_name,
            },
            status=status.HTTP_200_OK,
        )
class StudentsList(generics.ListAPIView):
    serializer_class = UserSerializer

    def get_queryset(self):
        # Get the "STUDENT" role object
        student_role = UserRole.objects.get(role_name="STUDENT")
        # Filter users who have that role
        return User.objects.filter(role=student_role)
    
class UsersList(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    