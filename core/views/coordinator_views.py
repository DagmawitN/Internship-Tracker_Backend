from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from core.permissions import IsCoordinatorUser
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError, PermissionDenied

from core.models import InternshipApplication

from rest_framework import serializers

class DepartmentReviewSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=[("approve", "Approve"), ("reject", "Reject")])

class DepartmentReviewView(APIView):
    permission_classes = [IsAuthenticated, IsCoordinatorUser]
    serializer_class = DepartmentReviewSerializer

    def patch(self, request, pk):
        application = get_object_or_404(InternshipApplication, pk=pk)

        coordinator = getattr(request.user, "staff", None)
        if not coordinator:
            raise PermissionDenied("You are not a department coordinator")

        if application.student.department != coordinator.department:
            raise PermissionDenied(
                "You can only review applications from your department"
            )

        if application.dept_status != "PENDING":
            raise ValidationError("Already reviewed")

        action = request.data.get("action")

        if action == "approve":
            application.dept_status = "APPROVED"
            application.mentor_status = "PENDING"

        elif action == "reject":
            application.dept_status = "REJECTED"

        else:
            raise ValidationError("Invalid action")

        application.save()

        return Response({"message": "Department review updated"})