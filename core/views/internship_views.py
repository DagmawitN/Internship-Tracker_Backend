from decimal import Decimal

from django.db.models import Case, Count, F, Q, Sum, Value, When
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import (
    Attendance,
    CompanyMentor,
    Internship,
    InternshipApplication,
    InternshipPosition,
    Supervisor,
)
from core.permissions import IsCompanyMentor, IsMentorOfCompany, IsStudentUser
from core.serializers.internship_serializer import (
    InternshipApplicationSerializer,
    InternshipNotesSerializer,
    InternshipPositionSerializer,
)
from core.services.notification_service import create_notification


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
            InternshipPosition, pk=self.kwargs["pk"], is_active=True
        )

        if InternshipApplication.objects.filter(
            student=self.request.user.student_profile, position=position
        ).exists():
            raise ValidationError("Already applied")

        serializer.save(student=self.request.user.student_profile, position=position)


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
        serializer.save(company=mentor.company)


class InternshipRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    serializer_class = InternshipPositionSerializer
    permission_classes = [IsAuthenticated, IsCompanyMentor, IsMentorOfCompany]
    queryset = InternshipPosition.objects.all()

    def perform_update(self, serializer):
        mentor = CompanyMentor.objects.get(user=self.request.user)

        if serializer.instance.company != mentor.company:
            raise PermissionDenied("You cannot update internships from another company")

        serializer.save()


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

        internships = Internship.objects.filter(
            position=position,
            status="NOT_STARTED",
        )

        if not internships.exists():
            raise ValidationError("No internships found for this position")

        today = timezone.now().date()
        if internships.filter(start_date__gt=today).exists():
            raise ValidationError("Cannot start before scheduled date")

        # Collect student users BEFORE bulk update for notification
        student_users = list(
            internships.select_related("student__user").values_list(
                "student__user_id", flat=True
            )
        )

        updated = internships.update(
            status="ONGOING",
            start_date=Case(
                When(start_date__isnull=True, then=Value(today)),
                default=F("start_date"),
            ),
        )

        # Notify each affected student
        from django.contrib.auth import get_user_model

        _User = get_user_model()
        for uid in student_users:
            try:
                user = _User.objects.get(pk=uid)
                create_notification(
                    recipient=user,
                    title="Internship Started",
                    message=f"Your internship for '{position.title}' has started.",
                    notification_type="INTERNSHIP_STATUS_CHANGED",
                    related_object_id=position.id,
                    related_object_type="InternshipPosition",
                )
            except _User.DoesNotExist:
                pass

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

        total_hours = Attendance.objects.filter(
            internship=internship,
        ).aggregate(total=Sum("total_hours"))["total"] or Decimal("0")

        internship.status = "COMPLETED"
        internship.end_date = timezone.now().date()
        internship.total_hours = total_hours
        internship.save(update_fields=["status", "end_date", "total_hours"])

        create_notification(
            recipient=internship.student.user,
            title="Internship Completed",
            message=f"Your internship for '{internship.position.title}' has been marked as completed.",
            notification_type="INTERNSHIP_STATUS_CHANGED",
            related_object_id=internship.id,
            related_object_type="Internship",
        )

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

        internship.status = "CANCELLED"
        internship.end_date = today
        internship.save(update_fields=["status", "end_date"])

        create_notification(
            recipient=internship.student.user,
            title="Internship Cancelled",
            message=f"Your internship for '{internship.position.title}' has been cancelled.",
            notification_type="INTERNSHIP_STATUS_CHANGED",
            related_object_id=internship.id,
            related_object_type="Internship",
        )

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
