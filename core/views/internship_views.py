from decimal import Decimal

from django.db.models import Case, Count, F, Q, Sum, Value, When
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.filters.internship_filters import InternshipFilter
from core.models import (
    Attendance,
    CompanyMentor,
    Internship,
    InternshipApplication,
    InternshipPosition,
    Staff,
    Supervisor,
)
from core.permissions import IsCompanyMentor, IsMentorOfCompany, IsStudentUser
from core.serializers.internship_serializer import (
    InternshipApplicationSerializer,
    InternshipNotesSerializer,
    InternshipPositionSerializer,
    InternshipRecordSerializer,
    StudentApplicationSerializer,
)
from core.services.notification_service import create_notification


def _internship_role(user):
    """Return the user's role_name or None."""
    return getattr(user.role, "role_name", None) if user.role else None


class InternshipApplicationCreateView(generics.CreateAPIView):
    serializer_class = InternshipApplicationSerializer
    permission_classes = [IsAuthenticated, IsStudentUser]

    def get_queryset(self):
        return InternshipApplication.objects.filter(
            student=self.request.user.student_profile
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        return context

    def perform_create(self, serializer):
        position = get_object_or_404(
            InternshipPosition.objects.select_related("company__mentor"),
            pk=self.kwargs["pk"],
            is_active=True,
        )

        if InternshipApplication.objects.filter(
            student=self.request.user.student_profile, position=position
        ).exists():
            raise ValidationError("Already applied")

        from core.services.application_service import build_form_snapshot
        from core.services.audit_service import log_audit_event

        student = self.request.user.student_profile

        requested_start = serializer.validated_data.get("requested_start_date")
        requested_end = serializer.validated_data.get("requested_end_date")
        working_days = serializer.validated_data.get("working_days_per_week")
        working_hours = serializer.validated_data.get("working_hours_per_day")

        snapshot = build_form_snapshot(
            student=student,
            position=position,
            requested_start_date=requested_start,
            requested_end_date=requested_end,
            working_days_per_week=working_days,
            working_hours_per_day=working_hours,
        )

        # Assign the position's company mentor automatically so they can
        # review the application without a separate assignment step.
        company_mentor = getattr(position.company, "mentor", None)

        application = serializer.save(
            student=student,
            position=position,
            mentor=company_mentor,
            form_snapshot=snapshot,
        )

        log_audit_event(
            actor=self.request.user,
            action="APPLICATION_SUBMITTED",
            target_type="InternshipApplication",
            target_id=application.id,
            description=(
                f"Student {self.request.user.email} applied for "
                f"'{position.title}' at '{position.company.company_name}'."
            ),
        )

        # Notify coordinator
        dept_staff = (
            Staff.objects.filter(department=student.department)
            .select_related("user")
            .first()
        )
        if dept_staff:
            create_notification(
                recipient=dept_staff.user,
                title="New Internship Application",
                message=(
                    f"Student {self.request.user.get_full_name() or self.request.user.email} "
                    f"applied for '{position.title}'. Please review."
                ),
                notification_type="INTERNSHIP_STATUS_CHANGED",
                related_object_id=application.id,
                related_object_type="InternshipApplication",
            )


class InternshipListCreateView(generics.ListCreateAPIView):
    serializer_class = InternshipPositionSerializer
    permission_classes = [IsAuthenticated]
    queryset = InternshipPosition.objects.all()

    def get_queryset(self):
        return InternshipPosition.objects.filter(is_active=True).annotate(
            accepted_applications=Count(
                "applications",
                filter=Q(applications__student_decision="ACCEPTED"),
                distinct=True,
            )
        )

    def perform_create(self, serializer):
        if not CompanyMentor.objects.filter(user=self.request.user).exists():
            raise PermissionDenied("Only company mentors can create internships")

        mentor = CompanyMentor.objects.get(user=self.request.user)
        position = serializer.save(company=mentor.company)

        from core.services.audit_service import log_audit_event

        log_audit_event(
            actor=self.request.user,
            action="INTERNSHIP_POSITION_CREATED",
            target_type="InternshipPosition",
            target_id=position.id,
            description=f"Position '{position.title}' created for {mentor.company.company_name}.",
        )


class InternshipRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    serializer_class = InternshipPositionSerializer
    permission_classes = [IsAuthenticated]
    queryset = InternshipPosition.objects.all()

    def perform_update(self, serializer):
        mentor = CompanyMentor.objects.filter(user=self.request.user).first()
        if not mentor:
            raise PermissionDenied(
                "Only company mentors can update internship positions"
            )

        if serializer.instance.company != mentor.company:
            raise PermissionDenied("You cannot update internships from another company")

        position = serializer.save()

        from core.services.audit_service import log_audit_event

        log_audit_event(
            actor=self.request.user,
            action="INTERNSHIP_POSITION_UPDATED",
            target_type="InternshipPosition",
            target_id=position.id,
            description=f"Position '{position.title}' updated by {self.request.user.email}.",
        )


class AvailableInternshipPositionListView(generics.ListAPIView):
    serializer_class = InternshipPositionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            InternshipPosition.objects.filter(is_active=True)
            .annotate(
                accepted_applications=Count(
                    "applications",
                    filter=Q(applications__student_decision="ACCEPTED"),
                    distinct=True,
                )
            )
            .filter(
                Q(max_applicants__isnull=True)
                | Q(accepted_applications__lt=F("max_applicants"))
            )
        )


class InternshipRecordListView(generics.ListAPIView):
    """
    GET /internship-records/

    Returns Internship execution records (not InternshipPosition job postings).
    Supports filtering, text search, and ordering.

    Role restrictions are applied in get_queryset() before filter backends run.
    """

    serializer_class = InternshipRecordSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = InternshipFilter
    search_fields = [
        "student__user__first_name",
        "student__user__last_name",
        "student__student_id",
        "company__company_name",
        "position__title",
    ]
    ordering_fields = ["start_date", "end_date", "status"]
    ordering = ["-start_date"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Internship.objects.none()

        user = self.request.user
        role = _internship_role(user)

        base_qs = Internship.objects.select_related(
            "student__user",
            "student__department",
            "student__advisor__user",
            "position",
            "position__company",
            "company",
            "mentor__user",
        )

        if role == "STUDENT":
            return base_qs.filter(student__user=user)

        if role == "ADVISOR":
            return base_qs.filter(student__advisor__user=user)

        if role == "COMPANY":
            mentor = CompanyMentor.objects.filter(user=user).first()
            if not mentor:
                return base_qs.none()
            return base_qs.filter(company=mentor.company)

        if role == "COORDINATOR":
            staff = getattr(user, "staff", None)
            if not staff:
                return base_qs.none()
            return base_qs.filter(student__department=staff.department)

        if role == "ADMIN":
            return base_qs.all()

        return base_qs.none()


class StartInternshipsByPositionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, position_id):
        position = get_object_or_404(InternshipPosition, pk=position_id)
        user = request.user
        is_admin = bool(user.role and user.role.role_name == "ADMIN")
        mentor = CompanyMentor.objects.filter(
            user=user, company=position.company
        ).first()

        if not is_admin and not mentor:
            raise PermissionDenied("Not authorized")

        today = timezone.now().date()
        if Internship.objects.filter(
            position=position, status="NOT_STARTED", start_date__gt=today
        ).exists():
            raise ValidationError("Cannot start before scheduled date")

        from core.services.lifecycle_service import start_internships_for_position

        updated = start_internships_for_position(position, actor=user)
        if updated == 0:
            raise ValidationError("No internships found for this position")

        return Response(
            {
                "message": "Internships started",
                "position_id": position.id,
                "started_count": updated,
            },
            status=status.HTTP_200_OK,
        )


class CompleteInternshipView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        internship = get_object_or_404(Internship, pk=pk)
        user = request.user
        mentor = CompanyMentor.objects.filter(
            user=user, company=internship.company
        ).first()
        coordinator = getattr(user, "staff", None)
        is_coordinator = bool(
            user.role
            and user.role.role_name == "COORDINATOR"
            and coordinator
            and coordinator.department_id == internship.student.department_id
        )

        if not mentor and not is_coordinator:
            raise PermissionDenied("Not authorized")

        if internship.status != "ONGOING":
            raise ValidationError("Internship must be ongoing")

        from core.services.lifecycle_service import complete_internship

        complete_internship(internship, actor=user)

        return Response(
            {
                "message": "Internship completed",
                "internship_id": internship.id,
                "total_hours": str(internship.total_hours),
            },
            status=status.HTTP_200_OK,
        )


class CancelInternshipView(APIView):
    permission_classes = [IsAuthenticated, IsStudentUser]

    def post(self, request, pk):
        internship = get_object_or_404(Internship, pk=pk)

        if internship.student_id != request.user.student_profile.id:
            raise PermissionDenied("Not your internship")

        today = timezone.now().date()
        if (
            internship.status != "NOT_STARTED"
            or not internship.start_date
            or today >= internship.start_date
        ):
            raise ValidationError("Cannot cancel after internship has started")

        from core.services.lifecycle_service import cancel_internship

        cancel_internship(internship, actor=request.user)

        return Response(
            {"message": "Internship cancelled", "internship_id": internship.id},
            status=status.HTTP_200_OK,
        )


class InternshipNotesView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = InternshipNotesSerializer

    def patch(self, request, pk):
        internship = get_object_or_404(Internship, pk=pk)
        user = request.user

        mentor_allowed = CompanyMentor.objects.filter(
            user=user,
            company=internship.company,
        ).exists()
        supervisor_allowed = Supervisor.objects.filter(
            user=user,
            id=internship.supervisor_id,
        ).exists()
        coordinator = getattr(user, "staff", None)
        coordinator_allowed = bool(
            user.role
            and user.role.role_name == "COORDINATOR"
            and coordinator
            and coordinator.department_id == internship.student.department_id
        )

        if not (mentor_allowed or supervisor_allowed or coordinator_allowed):
            raise PermissionDenied("Not authorized")

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_notes = serializer.validated_data["notes"]
        if serializer.validated_data["mode"] == "overwrite" or not internship.notes:
            internship.notes = new_notes
        else:
            internship.notes = f"{internship.notes}\n{new_notes}"

        internship.save(update_fields=["notes"])

        return Response(
            {
                "message": "Internship notes updated",
                "internship_id": internship.id,
                "notes": internship.notes,
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Student: list own applications
# ---------------------------------------------------------------------------


class StudentApplicationsListView(generics.ListAPIView):
    """GET /applications/my/ — paginated list of the student's applications."""

    serializer_class = StudentApplicationSerializer
    permission_classes = [IsAuthenticated, IsStudentUser]

    def get_queryset(self):
        return (
            InternshipApplication.objects.filter(
                student=self.request.user.student_profile
            )
            .select_related(
                "position",
                "position__company",
                "advisor__user",
            )
            .order_by("-created_at")
        )
