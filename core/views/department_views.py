from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from core.models import Department
from core.serializers.department_serializer import DepartmentSerializer


class DepartmentViewSet(viewsets.ModelViewSet):
    """
    CRUD API for departments.
    """

    queryset = Department.objects.all().order_by("department_name")
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]
