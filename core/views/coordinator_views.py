from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import InternshipApplication,Staff
from core.permissions import IsCoordinatorUser


class DepartmentReviewSerializer(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=[("approve", "Approve"), ("reject", "Reject")]
    )
    signature = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text="Coordinator's full name as digital signature.",
    )


class DepartmentReviewView(APIView):
    """
    PATCH /applications/{pk}/dept-review/

    Coordinator-first step of the internship application workflow.
    Coordinator approves or rejects. On approval, a digital signature is stored
    and the application is forwarded to the company mentor.
    """

    permission_classes = [IsAuthenticated, IsCoordinatorUser]
    serializer_class = DepartmentReviewSerializer

    def patch(self, request, pk):
        application = get_object_or_404(InternshipApplication, pk=pk)

        coordinator = Staff.objects.filter(user=request.user).first()
    
        if not coordinator:
            raise PermissionDenied("You are not a department coordinator.")

        if application.student.department != coordinator.department:
            raise PermissionDenied(
                "You can only review applications from your department."
            )

        serializer = DepartmentReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action = serializer.validated_data["action"]
        signature = serializer.validated_data.get("signature", "")

        from core.services.application_service import process_coordinator_review

        try:
           
            process_coordinator_review(
                application=application,
                actor=request.user,
                action=action,
                signature=signature,
            )
        except ValueError as exc:
            raise ValidationError(str(exc))

        return Response(
            {
                "message": f"Application {action}d by coordinator.",
                "application_id": application.id,
                "coordinator_status": application.dept_status,
                "coordinator_signed_at": application.coordinator_signed_at,
            },
            status=status.HTTP_200_OK,
        )
