from django.shortcuts import get_object_or_404
from django.db import models
from django.db.models import Count
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import (
    Advisor,
    AdvisorAssignment,
    Internship,
    InternshipApplication,
    Student,
)
from core.permissions import IsAdvisorUser, IsCoordinatorUser, IsExaminerUser
from core.serializers.advisor_serializer import (
    AdvisorNotesSerializer,
    AdvisorReviewSerializer,
    AdvisorSerializer,
    AssignAdvisorSerializer,
    AssignExaminerSerializer,
)


def _get_role(user):
    return getattr(user.role, "role_name", None) if user.role else None


def _resolve_student_current_application(student):
    """Resolve the application that corresponds to the student's current placement."""
    active_internship = (
        Internship.objects.filter(
            student=student,
            status__in=["NOT_STARTED", "ONGOING"],
        )
        .select_related("position")
        .order_by("-id")
        .first()
    )

    if active_internship and active_internship.position_id:
        matched = (
            InternshipApplication.objects.filter(
                student=student,
                position_id=active_internship.position_id,
            )
            .filter(
                models.Q(student_decision="ACCEPTED")
                | models.Q(dept_status="APPROVED")
                | models.Q(mentor_status="ACCEPTED")
            )
            .order_by("-created_at")
            .first()
        )
        if matched:
            return matched

    return (
        InternshipApplication.objects.filter(student=student)
        .filter(
            models.Q(student_decision="ACCEPTED")
            | models.Q(dept_status="APPROVED")
            | models.Q(mentor_status="ACCEPTED")
        )
        .order_by("-created_at")
        .first()
    )


# ---------------------------------------------------------------------------
# Coordinator: list advisors in own department
# ---------------------------------------------------------------------------


class AdvisorListView(generics.ListAPIView):
    """GET /advisors/ — list advisors, optionally limited to unassigned ones."""

    serializer_class = AdvisorSerializer
    permission_classes = [IsAuthenticated, IsCoordinatorUser]

    def get_queryset(self):
        token = getattr(self.request, "auth", None)
        department_id = None

        if token:
            if hasattr(token, "get"):
                department_id = token.get("department_id")
            else:
                department_id = getattr(token, "department_id", None)

        if not department_id:
            staff = getattr(self.request.user, "staff", None)
            if staff:
                department_id = staff.department_id

        queryset = (
            Advisor.objects.filter(department_id=department_id)
            .select_related("user", "department")
            .prefetch_related("assigned_students")
        )

        # Support filtering by unassigned advisors if requested.
        unassigned = self.request.query_params.get("unassigned", "").lower() == "true"
        if unassigned:
            queryset = queryset.annotate(
                assigned_count=Count("assigned_students")
            ).filter(assigned_count=0)

        return queryset


# ---------------------------------------------------------------------------
# Coordinator: assign advisor to student
# ---------------------------------------------------------------------------


class AssignAdvisorView(APIView):
    """POST /students/{pk}/assign-advisor/
       DELETE /students/{pk}/assign-advisor/  — remove advisor assignment
    """

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

        # advisor_id is the User PK of the staff member
        advisor = Advisor.objects.filter(user_id=advisor_id).first()
        if not advisor:
            raise ValidationError("No Advisor profile found for the given user. Ensure the staff member has the ADVISOR role.")

        # Enforce same-department rule for advisor
        if advisor.department != coordinator_staff.department:
            raise ValidationError("Advisor does not belong to your department.")

        # Assign advisor to student
        student.advisor = advisor
        student.save(update_fields=["advisor"])

        # Link advisor to all active applications for this student
        updated = InternshipApplication.objects.filter(
            student=student,
        ).filter(
            models.Q(dept_status="APPROVED") | models.Q(student_decision="ACCEPTED")
        ).update(advisor=advisor)

        from core.services.audit_service import log_audit_event

        log_audit_event(
            actor=request.user,
            action="ADVISOR_ASSIGNED",
            target_type="Student",
            target_id=student.id,
            description=f"Advisor '{advisor.user.email}' assigned to student '{student.user.email}'.",
        )

        return Response(
            {
                "message": "Advisor assigned successfully.",
                "student_id": student.id,
                "advisor_id": advisor.id,
                "applications_linked": updated,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk):
        """Remove advisor assignment from a student."""
        student = get_object_or_404(Student, user__id=pk)

        coordinator_staff = getattr(request.user, "staff", None)
        if not coordinator_staff:
            raise PermissionDenied("You are not a department coordinator.")

        if student.department != coordinator_staff.department:
            raise PermissionDenied("This student is not in your department.")

        student.advisor = None
        student.save(update_fields=["advisor"])

        from core.services.audit_service import log_audit_event

        log_audit_event(
            actor=request.user,
            action="ADVISOR_REMOVED",
            target_type="Student",
            target_id=student.id,
            description=f"Advisor removed from student '{student.user.email}'.",
        )

        return Response(
            {
                "message": "Advisor assignment removed.",
                "student_id": student.id,
            },
            status=status.HTTP_200_OK,
        )


class AssignExaminerView(APIView):
    """POST /students/{pk}/assign-examiner/
       DELETE /students/{pk}/assign-examiner/  — remove examiner assignment
    """

    permission_classes = [IsAuthenticated, IsCoordinatorUser]
    serializer_class = AssignExaminerSerializer

    def post(self, request, pk):
        # pk = User pk of the student
        student = get_object_or_404(Student, user__id=pk)

        coordinator_staff = getattr(request.user, "staff", None)
        if not coordinator_staff:
            raise PermissionDenied("You are not a department coordinator.")

        # Enforce same-department rule for student
        if student.department != coordinator_staff.department:
            raise PermissionDenied("This student is not in your department.")

        serializer = AssignExaminerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        examiner_id = serializer.validated_data["examiner_id"]

        # examiner_id is the User PK — look up the User directly (examiners don't have Advisor profiles)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        examiner_user = get_object_or_404(User, pk=examiner_id)

        # Verify the user belongs to the coordinator's department via Staff record
        examiner_staff = getattr(examiner_user, "staff", None)
        if not examiner_staff or examiner_staff.department != coordinator_staff.department:
            raise ValidationError("Examiner does not belong to your department.")

        # Resolve the application tied to the student's active placement first.
        application = _resolve_student_current_application(student)

        if not application:
            raise ValidationError(
                "No accepted internship application found for this student."
            )

        # Create AdvisorAssignment with EXAMINER role — allow multiple examiners per application
        assignment, created = AdvisorAssignment.objects.get_or_create(
            internship=application,
            advisor=examiner_user,
            defaults={
                "role": "EXAMINER",
                "coordinator": request.user,
                "student": student.user,
            },
        )
        if not created:
            # Already assigned — ensure role is EXAMINER
            assignment.role = "EXAMINER"
            assignment.save(update_fields=["role"])

        from core.services.audit_service import log_audit_event

        log_audit_event(
            actor=request.user,
            action="EXAMINER_ASSIGNED",
            target_type="Student",
            target_id=student.id,
            description=(
                f"Examiner '{examiner_user.email}' assigned to student "
                f"'{student.user.email}' for application {application.id}."
            ),
        )

        return Response(
            {
                "message": "Examiner assigned successfully.",
                "student_id": student.id,
                "examiner_user_id": examiner_user.id,
                "application_id": application.id,
                "assignment_id": assignment.id,
                "created": created,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk):
        """Remove examiner assignment for a student."""
        student = get_object_or_404(Student, user__id=pk)

        coordinator_staff = getattr(request.user, "staff", None)
        if not coordinator_staff:
            raise PermissionDenied("You are not a department coordinator.")

        if student.department != coordinator_staff.department:
            raise PermissionDenied("This student is not in your department.")

        application = _resolve_student_current_application(student)

        if not application:
            raise ValidationError(
                "No accepted internship application found for this student."
            )

        # If examiner_id provided, remove only that specific examiner; otherwise remove all
        examiner_id = request.data.get("examiner_id") if hasattr(request, "data") else None
        qs = AdvisorAssignment.objects.filter(internship=application, role="EXAMINER")
        if examiner_id:
            qs = qs.filter(advisor_id=examiner_id)
        deleted_count, _ = qs.delete()

        log_audit_event(
            actor=request.user,
            action="EXAMINER_REMOVED",
            target_type="Student",
            target_id=student.id,
            description=(
                f"Examiner removed from student '{student.user.email}' "
                f"for application {application.id}."
            ),
        )

        return Response(
            {
                "message": "Examiner assignment removed.",
                "student_id": student.id,
                "application_id": application.id,
                "deleted_count": deleted_count,
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

        from core.services.audit_service import log_audit_event
        from core.services.notification_service import create_notification

        log_audit_event(
            actor=request.user,
            action="APPLICATION_ADVISOR_REVIEWED",
            target_type="InternshipApplication",
            target_id=application.id,
            description=(
                f"Advisor {request.user.email} {action}d application {application.id} "
                f"for student {application.student.user.email}."
            ),
        )

        # Notify the student of the advisor's decision
        create_notification(
            recipient=application.student.user,
            title="Advisor Review Complete",
            message=(
                f"Your application for '{application.position.title}' has been "
                f"{'approved' if action == 'approve' else 'rejected'} by your advisor."
            ),
            notification_type="INTERNSHIP_STATUS_CHANGED",
            related_object_id=application.id,
            related_object_type="InternshipApplication",
        )

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


# ---------------------------------------------------------------------------
# Advisor: list students assigned to the logged-in advisor
# ---------------------------------------------------------------------------


class AdvisorMyStudentsView(generics.ListAPIView):
    """GET /advisor/my-students/
    Returns all internship applications for students assigned to the
    currently authenticated advisor, including examiner assignments.
    """

    permission_classes = [IsAuthenticated, IsAdvisorUser]

    def get_serializer_class(self):
        from core.serializers.internship_serializer import InternshipRequestFormSerializer
        return InternshipRequestFormSerializer

    def get_queryset(self):
        advisor = get_object_or_404(Advisor, user=self.request.user)
        return (
            InternshipApplication.objects.filter(
                advisor=advisor,
                student_decision="ACCEPTED",
            )
            .select_related(
                "student__user",
                "student__department",
                "student__advisor__user",
                "position",
                "position__company",
                "advisor__user",
            )
            .order_by("-created_at")
        )



# ---------------------------------------------------------------------------
# Examiner: list students assigned to the logged-in examiner
# ---------------------------------------------------------------------------


class ExaminerMyStudentsView(generics.ListAPIView):
    """GET /examiner/my-students/
    Returns all internship applications for students assigned to the
    currently authenticated examiner via AdvisorAssignment (role=EXAMINER).
    """

    permission_classes = [IsAuthenticated, IsExaminerUser]

    def get_serializer_class(self):
        from core.serializers.internship_serializer import InternshipRequestFormSerializer
        return InternshipRequestFormSerializer

    def get_queryset(self):
        # Get all application IDs where this user is assigned as EXAMINER
        assigned_app_ids = AdvisorAssignment.objects.filter(
            advisor=self.request.user,
            role="EXAMINER",
        ).values_list("internship_id", flat=True)

        return (
            InternshipApplication.objects.filter(
                id__in=assigned_app_ids,
            )
            .select_related(
                "student__user",
                "student__department",
                "student__advisor__user",
                "position",
                "position__company",
                "advisor__user",
            )
            .order_by("-created_at")
        )
