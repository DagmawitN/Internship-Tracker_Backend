from django.contrib.auth import get_user_model
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import Advisor, UserRole
from core.permissions import IsAdminUser, IsCoordinatorUser, IsStudentUser
from core.serializers.auth_serializers import UserSerializer
from core.serializers.user_serializers import AssignRoleSerializer

User = get_user_model()


class UserViewSet(viewsets.GenericViewSet):
    queryset = User.objects.all()
    serializer_class = AssignRoleSerializer
    permission_classes = [IsAuthenticated]

    @action(
        detail=False,
        methods=["post"],
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
        methods=["post"],
        permission_classes=[IsCoordinatorUser],
        url_name="coordinator_assign_role",
    )
    def coordinator_assign_role(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        role = serializer.validated_data["role"]

        if role.role_name not in ["ADVISOR", "EXAMINER"]:
            return Response(
                {"error": "Coordinators cannot assign that role."},
                status=status.HTTP_403_FORBIDDEN,
            )

        user.role = role
        user.save()

        coordinator = getattr(request.user, "staff", None)
        if not coordinator:
            return Response(
                {"error": "Coordinator profile not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        advisor = None

        if role.role_name == "ADVISOR":
            advisor, created = Advisor.objects.get_or_create(
                user=user, defaults={"department": coordinator.department}
            )

        return Response(
            {
                "message": f"User '{user.username}' assigned as '{role.role_name}'",
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "role": role.role_name,
                "advisor_id": advisor.id if advisor else None,
            },
            status=status.HTTP_200_OK,
        )


class StudentsList(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return User.objects.filter(role__role_name="STUDENT")


class UsersList(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
