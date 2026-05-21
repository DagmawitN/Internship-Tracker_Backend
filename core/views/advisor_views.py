from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Advisor, AdvisorAssignment, Internship, InternshipApplication, Student
from core.permissions import IsAdvisorUser, IsCoordinatorUser
from core.serializers.advisor_serializer import (
    AdvisorNotesSerializer,
    AdvisorReviewSerializer,
    AdvisorSerializer,
    AssignAdvisorSerializer,
)


def _get_role(user):
    return getattr(user.role, "role_name", None) if user.role else None


# ---------------------------------------------------------------------------
# Coordinator: list advisors in own department
# ---------------------------------------------------------------------------


class AdvisorListView(generics.ListAPIView):
    """GET /advisors/  — coordinator sees all advisors in their department."""

    serializer_class = AdvisorSerializer
    permission_classes = [IsAuthenticated, IsCoordinatorUser]

    def get_queryset(self):
        staff = getattr(self.request.user, "staff", None)
        if not staff:
            return Advisor.objects.none()
        return (
            Advisor.objects.filter(department=staff.department)
            .select_related("user", "department")
            .prefetch_related("assigned_students")
        )


# ---------------------------------------------------------------------------
# Coordinator: assign advisor to student
# ---------------------------------------------------------------------------


class AssignAdvisorView(APIView):
    """POST /students/{pk}/assign-advisor/"""

    permission_classes = [IsAuthenticated, IsCoordinatorUser]
    serializer_class = AssignAdvisorSerializer

    def post(self, request, pk):
        # pk = User pk of the student (consistent with existing /students/ list)
        student = get_object_or_404(Student, user__id=pk)

        coordinator_staff = getattr(request.user, "staff", None)
        if not coordinator_staff:
            raise PermissionDenied("You are not a department coordinator.")

        # Enforce same-department rule for student
        if student.department != coordinator_staff.department:
            raise PermissionDenied("This student is not in your department.")

        serializer = AssignAdvisorSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        advisor_id = serializer.validated_data["advisor_id"]

        advisor = get_object_or_404(Advisor, pk=advisor_id)

        # Enforce same-department rule for advisor
        if advisor.department != coordinator_staff.department:
            raise ValidationError("Advisor does not belong to your department.")

        # Assign advisor to student
        student.advisor = advisor
        student.save(update_fields=["advisor"])

        # Auto-link advisor to applications where mentor accepted but advisor not yet assigned
        pending_apps = list(
            InternshipApplication.objects.filter(
                student=student,
                mentor_status="ACCEPTED",
                advisor__isnull=True,
            )
        )
        for application in pending_apps:
            application.advisor = advisor
            application.dept_status = "APPROVED"
            application.save(update_fields=["advisor", "dept_status"])
            AdvisorAssignment.objects.get_or_create(
                advisor=advisor.user,
                student=student.user,
                internship=application,
                defaults={"role": "ADVISOR"},
            )
        updated = len(pending_apps)

        return Response(
            {
                "message": "Advisor assigned successfully.",
                "student_id": student.id,
                "advisor_id": advisor.id,
                "applications_linked": updated,
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Advisor: review internship application
# ---------------------------------------------------------------------------


class AdvisorReviewView(APIView):
    """POST /applications/{pk}/advisor-review/"""

    permission_classes = [IsAuthenticated, IsAdvisorUser]
    serializer_class = AdvisorReviewSerializer

    def post(self, request, pk):
        application = get_object_or_404(InternshipApplication, pk=pk)

        advisor = get_object_or_404(Advisor, user=request.user)

        # Advisor must be assigned to this student
        if application.student.advisor_id != advisor.pk:
            raise PermissionDenied("You are not assigned to this student.")

        # Same department check
        if advisor.department != application.student.department:
            raise PermissionDenied("Department mismatch.")

        # Mentor must have accepted first
        if application.mentor_status != "ACCEPTED":
            raise ValidationError(
                "Company mentor has not accepted this application yet."
            )

        # Prevent double review
        if application.advisor_status != "PENDING":
            raise ValidationError("You have already reviewed this application.")

        serializer = AdvisorReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action = serializer.validated_data["action"]
        notes = serializer.validated_data.get("notes", "")

        application.advisor = advisor
        if action == "approve":
            application.advisor_status = "APPROVED"
        else:
            application.advisor_status = "REJECTED"

        if notes:
            application.advisor_notes = notes

        application.save(update_fields=["advisor", "advisor_status", "advisor_notes"])

        return Response(
            {
                "message": f"Application {action}d by advisor.",
                "application_id": application.id,
                "advisor_status": application.advisor_status,
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Advisor: add notes to an internship
# ---------------------------------------------------------------------------


class AdvisorInternshipNotesView(APIView):
    """PATCH /internships/{pk}/advisor-notes/"""

    permission_classes = [IsAuthenticated, IsAdvisorUser]
    serializer_class = AdvisorNotesSerializer

    def patch(self, request, pk):
        internship = get_object_or_404(Internship, pk=pk)

        advisor = get_object_or_404(Advisor, user=request.user)

        # Advisor must be assigned to the internship's student
        if internship.student.advisor_id != advisor.pk:
            raise PermissionDenied("You are not assigned to this student.")

        # Same department check
        if advisor.department != internship.student.department:
            raise PermissionDenied("Department mismatch.")

        serializer = AdvisorNotesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_notes = serializer.validated_data["notes"]
        mode = serializer.validated_data.get("mode", "append")

        if mode == "overwrite" or not internship.notes:
            internship.notes = new_notes
        else:
            internship.notes = f"{internship.notes}\n{new_notes}"

        internship.save(update_fields=["notes"])

        return Response(
            {
                "message": "Internship notes updated.",
                "internship_id": internship.id,
                "notes": internship.notes,
            },
            status=status.HTTP_200_OK,
        )
