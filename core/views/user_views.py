from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Advisor, Department, PreRegisteredStudent, Staff, UserRole
from core.permissions import IsAdminUser, IsCoordinatorUser, IsStudentUser
from core.serializers.auth_serializers import UserSerializer
from core.serializers.user_serializers import AssignRoleSerializer

User = get_user_model()

COORDINATOR_MANAGED_ROLES = {"ADVISOR", "EXAMINER", "COORDINATOR"}


def _mark_staff_assigned(user):
    staff = getattr(user, "staff", None)
    if staff:
        staff.is_assigned = True
        staff.save(update_fields=["is_assigned", "updated_at"])


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

        if role.role_name in COORDINATOR_MANAGED_ROLES:
            _mark_staff_assigned(user)

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

        if role.role_name not in COORDINATOR_MANAGED_ROLES:
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

        _mark_staff_assigned(user)

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


class StudentsList(generics.ListCreateAPIView):
    """GET: list students (optionally filter by department and status)
       POST: create a student (coordinator or admin)
    """
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        return UserSerializer

    def get_permissions(self):
        # allow any authenticated user to GET, but only coordinators/admins to POST
        if self.request.method == "POST":
            return [IsAuthenticated(), IsCoordinatorUser()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = User.objects.filter(role__role_name="STUDENT").select_related(
            "student_profile",
            "student_profile__department",
        )
        dept = self.request.query_params.get("department")
        status = self.request.query_params.get("status")

        # Coordinators can only see students from their own department.
        if IsCoordinatorUser().has_permission(self.request, self):
            coordinator = getattr(self.request.user, "staff", None)
            if not coordinator or not coordinator.department_id:
                return qs.none()

            qs = qs.filter(student_profile__department_id=coordinator.department_id)

            # If a department query is provided, do not allow cross-department reads.
            if dept:
                requested_department = _resolve_department_value(dept)
                if requested_department and requested_department.id != coordinator.department_id:
                    return qs.none()
        elif dept:
            requested_department = _resolve_department_value(dept)
            if requested_department:
                qs = qs.filter(student_profile__department_id=requested_department.id)
            else:
                qs = qs.filter(student_profile__department__department_name__iexact=dept)

        if status and str(status).strip().lower() == "approved":
            # students with at least one approved internship application
            qs = qs.filter(student_profile__applications__dept_status__iexact="APPROVED").distinct()

        return qs

    def create(self, request, *args, **kwargs):
        # Use StudentRegistrationSerializer to create both User and Student
        from core.serializers.auth_serializers import StudentRegistrationSerializer

        serializer = StudentRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        student = serializer.save()
        # Return the serialized user info for compatibility with frontend expectations
        user_ser = UserSerializer(student.user)
        return Response(user_ser.data, status=status.HTTP_201_CREATED)


class UsersList(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]


def _resolve_department_value(value):
    department_value = str(value or "").strip()
    if not department_value:
        return None

    department = None
    if department_value.isdigit():
        department = Department.objects.filter(pk=int(department_value)).first()
    if not department:
        department = Department.objects.filter(department_name__iexact=department_value).first()
    if not department:
        department = Department.objects.filter(department_code__iexact=department_value).first()
    return department


class EligibleStudentBulkUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def _serialize_student(self, student):
        return {
            "id": student.id,
            "name": student.name,
            "studentId": student.student_id,
            "email": student.email,
            "department": student.department.department_name,
        }

    def get(self, request):
        if not (IsCoordinatorUser().has_permission(request, self) or IsAdminUser().has_permission(request, self)):
            return Response(
                {"error": "You do not have permission to view eligible students."},
                status=status.HTTP_403_FORBIDDEN,
            )

        department = _resolve_department_value(request.query_params.get("department"))
        queryset = PreRegisteredStudent.objects.select_related("department").order_by("name")
        if department:
            queryset = queryset.filter(department=department)

        return Response(
            [self._serialize_student(student) for student in queryset],
            status=status.HTTP_200_OK,
        )

    @transaction.atomic
    def post(self, request):
        if not (IsCoordinatorUser().has_permission(request, self) or IsAdminUser().has_permission(request, self)):
            return Response(
                {"error": "You do not have permission to upload eligible students."},
                status=status.HTTP_403_FORBIDDEN,
            )

        payload = request.data
        rows = payload.get("students") if isinstance(payload, dict) else payload
        if not isinstance(rows, list) or not rows:
            return Response(
                {"error": "Expected a non-empty JSON array of students."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        imported = []
        for index, item in enumerate(rows):
            if not isinstance(item, dict):
                return Response(
                    {"error": f"Row {index + 1} must be an object."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            student_id = str(item.get("studentId") or item.get("student_id") or item.get("id") or "").strip()
            name = str(item.get("fullName") or item.get("full_name") or item.get("name") or "").strip()
            department = _resolve_department_value(item.get("department"))

            if not student_id or not name or not department:
                return Response(
                    {
                        "error": f"Row {index + 1} must include studentId, fullName, and a valid department.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            student, _ = PreRegisteredStudent.objects.update_or_create(
                student_id=student_id,
                defaults={
                    "name": name,
                    "email": str(item.get("email") or "").strip(),
                    "department": department,
                },
            )
            imported.append(self._serialize_student(student))

        return Response(
            {
                "message": f"Imported {len(imported)} eligible student(s).",
                "count": len(imported),
                "students": imported,
            },
            status=status.HTTP_201_CREATED,
        )
