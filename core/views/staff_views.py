from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Department, Staff
from core.permissions import IsAdminUser, IsCoordinatorUser
from core.serializers.staff_serializers import DepartmentQuerySerializer, StaffSerializer


class IsAdminOrCoordinator:
    def has_permission(self, request, view):
        return bool(
            IsAdminUser().has_permission(request, view)
            or IsCoordinatorUser().has_permission(request, view)
        )


def _resolve_department(request):
    params = DepartmentQuerySerializer(data=request.query_params)
    params.is_valid(raise_exception=True)

    department_value = (params.validated_data.get("department") or "").strip()
    if department_value:
        department = None
        if department_value.isdigit():
            department = Department.objects.filter(pk=int(department_value)).first()
        if not department:
            department = Department.objects.filter(
                department_name__iexact=department_value
            ).first()
        if not department:
            department = Department.objects.filter(
                department_code__iexact=department_value
            ).first()
        if not department:
            raise ValidationError({"department": "Invalid department value."})
        return department

    staff = getattr(request.user, "staff", None)
    if staff and IsCoordinatorUser().has_permission(request, None):
        return staff.department

    raise ValidationError({"department": "This query parameter is required."})


class StaffUnassignedListView(generics.ListAPIView):
    serializer_class = StaffSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        department = _resolve_department(self.request)

        if IsCoordinatorUser().has_permission(self.request, self):
            staff = getattr(self.request.user, "staff", None)
            if staff and staff.department_id != department.id:
                raise PermissionDenied("You can only access your own department.")

        return Staff.objects.filter(department=department, is_assigned=False).select_related(
            "user", "department", "user__role"
        )


class StaffAssignedListView(generics.ListAPIView):
    serializer_class = StaffSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        department = _resolve_department(self.request)

        if IsCoordinatorUser().has_permission(self.request, self):
            staff = getattr(self.request.user, "staff", None)
            if staff and staff.department_id != department.id:
                raise PermissionDenied("You can only access your own department.")

        return Staff.objects.filter(department=department, is_assigned=True).select_related(
            "user", "department", "user__role"
        )


class StaffAssignView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not (IsAdminUser().has_permission(request, self) or IsCoordinatorUser().has_permission(request, self)):
            raise PermissionDenied("You do not have permission to assign staff.")

        staff = get_object_or_404(Staff, pk=pk)
        department = _resolve_department(request)

        if IsCoordinatorUser().has_permission(request, self):
            coordinator = getattr(request.user, "staff", None)
            if not coordinator or coordinator.department_id != department.id:
                raise PermissionDenied("You can only assign staff from your own department.")

        if staff.department_id != department.id:
            raise PermissionDenied("Staff member does not belong to the selected department.")

        staff.is_assigned = True
        staff.save(update_fields=["is_assigned", "updated_at"])

        return Response(
            {"message": "Staff marked as assigned.", "staff": StaffSerializer(staff).data},
            status=status.HTTP_200_OK,
        )


class StaffUnassignView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not (IsAdminUser().has_permission(request, self) or IsCoordinatorUser().has_permission(request, self)):
            raise PermissionDenied("You do not have permission to unassign staff.")

        staff = get_object_or_404(Staff, pk=pk)
        department = _resolve_department(request)

        if IsCoordinatorUser().has_permission(request, self):
            coordinator = getattr(request.user, "staff", None)
            if not coordinator or coordinator.department_id != department.id:
                raise PermissionDenied("You can only unassign staff from your own department.")

        if staff.department_id != department.id:
            raise PermissionDenied("Staff member does not belong to the selected department.")

        staff.is_assigned = False
        staff.save(update_fields=["is_assigned", "updated_at"])

        return Response(
            {"message": "Staff marked as unassigned.", "staff": StaffSerializer(staff).data},
            status=status.HTTP_200_OK,
        )