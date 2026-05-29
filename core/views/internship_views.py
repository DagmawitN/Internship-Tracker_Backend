from decimal import Decimal

from django.db.models import Case, Count, F, Q, Sum, Value, When
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from core.filters.internship_filters import InternshipFilter
from core.models import (
    Attendance,
    Company,
    CompanyEvaluationStatus,
    CompanyMentor,
    Internship,
    InternshipApplication,
    InternshipPosition,
    SelfPlacementRequest,
    Staff,
    Supervisor,
)
from core.permissions import IsCompanyMentor, IsCoordinatorUser, IsMentorOfCompany, IsStudentUser
from core.serializers.internship_serializer import (
    InternshipApplicationSerializer,
    InternshipNotesSerializer,
    InternshipPositionSerializer,
    InternshipRecordSerializer,
    InternshipRequestFormSerializer,
    StudentApplicationSerializer,
)
from core.serializers.company_serializer import CompanyApplicationSerializer
from core.serializers.self_placement_serializer import SelfPlacementRequestSerializer
from core.services.notification_service import create_notification


def _internship_role(user):
    """Return the user's role_name or None."""
    role = getattr(user, "role", None)
    if not role:
        return None
    if isinstance(role, str):
        return role.strip().upper()
    role_name = getattr(role, "role_name", None)
    return str(role_name).strip().upper() if role_name else None


def _company_for_user(user):
    mentor = CompanyMentor.objects.filter(user=user).select_related("company").first()
    if mentor:
        return mentor.company

    if str(_internship_role(user)).upper() == "COMPANY":
        company = Company.objects.filter(
            contact_email=user.email, is_active=True
        ).first()
        if company:
            return company

        mentor_by_company_email = (
            CompanyMentor.objects.filter(company__contact_email=user.email)
            .select_related("company")
            .first()
        )
        if mentor_by_company_email:
            return mentor_by_company_email.company

    return None


def _require_company_user_id(user, company_id):
    if not user or not user.is_authenticated:
        raise PermissionDenied("Authentication required")

    company = _company_for_user(user)
    if not company:
        raise PermissionDenied("Only company users can manage internships")

    if str(company.id) != str(company_id):
        raise PermissionDenied("You can only manage internships for your own company")

    if _internship_role(user) != "COMPANY":
        raise PermissionDenied("Only company users can manage internships")

    return company


def _sync_application_advisor_status_from_final_eval(application):
    """Best-effort sync so application advisor_status reflects final company evaluation state."""
    if not application or application.advisor_status != "PENDING":
        return application

    internship = (
        Internship.objects.filter(
            student=application.student,
            position=application.position,
        )
        .select_related("final_industry_evaluation")
        .order_by("-id")
        .first()
    )
    if not internship:
        return application

    final_eval = getattr(internship, "final_industry_evaluation", None)
    if not final_eval:
        return application

    if final_eval.status == CompanyEvaluationStatus.ADVISOR_APPROVED:
        application.advisor_status = "APPROVED"
    elif final_eval.status == CompanyEvaluationStatus.REJECTED:
        application.advisor_status = "REJECTED"
    else:
        return application

    update_fields = ["advisor_status"]
    if not application.advisor_id and getattr(application.student, "advisor_id", None):
        application.advisor_id = application.student.advisor_id
        update_fields.append("advisor")

    application.save(update_fields=update_fields)
    return application


def _self_placement_to_application_like(request_obj):
    serializer = SelfPlacementRequestSerializer(request_obj)
    data = serializer.data
    student = request_obj.student
    student_user = student.user
    advisor_user = student.advisor.user if getattr(student, "advisor", None) and student.advisor.user else None

    return {
        "id": request_obj.id,
        "student_name": data.get("student_name") or student_user.get_full_name().strip() or student_user.username,
        "student_email": student_user.email,
        "student_user_id": student_user.id,
        "student_id": data.get("student_id") or student.student_id,
        "position_title": "Self Placement",
        "company_name": request_obj.company_name,
        "company_id": None,
        "work_mode": "SELF_PLACEMENT",
        "overall_status": request_obj.status,
        "dept_status": request_obj.status,
        "mentor_status": None,
        "advisor_status": "APPROVED" if request_obj.status == SelfPlacementRequest.Status.APPROVED else "PENDING",
        "student_decision": "PENDING",
        "rejection_reason": request_obj.review_notes or "",
        "requested_start_date": None,
        "requested_end_date": None,
        "working_days_per_week": None,
        "working_hours_per_day": None,
        "coordinator_signature": "",
        "coordinator_signed_at": request_obj.reviewed_at,
        "mentor_signature": "",
        "mentor_signed_at": None,
        "form_snapshot": {
            "student": {
                "name": data.get("student_name") or student_user.get_full_name().strip() or student_user.username,
                "student_id": student.student_id,
                "email": student_user.email,
                "department": student.department.department_name if student.department else "",
                "statement": request_obj.additional_notes or "",
                "resume_url": student.resume.url if getattr(student, "resume", None) else "",
            },
            "company": {
                "name": request_obj.company_name,
                "representative_name": request_obj.representative_name,
                "email": request_obj.representative_email,
                "phone": request_obj.representative_phone,
                "location": request_obj.location,
                "license_url": data.get("company_license_url") or "",
            },
            "mentor": {
                "name": request_obj.representative_name,
                "email": request_obj.representative_email,
                "phone": request_obj.representative_phone,
            },
            "internship": {
                "position_title": "Self Placement",
                "work_mode": "SELF_PLACEMENT",
            },
        },
        "advisor_name": advisor_user.get_full_name().strip() or advisor_user.username if advisor_user else "",
        "resume_url": student.resume.url if getattr(student, "resume", None) else None,
        "company_license_url": data.get("company_license_url") or None,
        "created_at": request_obj.created_at.isoformat() if request_obj.created_at else None,
        "is_self_placement": True,
        "finalInternshipStatus": "ACTIVE_INTERN" if request_obj.status == SelfPlacementRequest.Status.APPROVED else "PENDING",
        "studentUserPk": student_user.id,
        "__raw": {
            "selfPlacementRequest": data,
        },
    }


class InternshipApplicationCreateView(generics.CreateAPIView):
    serializer_class = InternshipApplicationSerializer
    permission_classes = [IsAuthenticated, IsStudentUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

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
        queryset = InternshipPosition.objects.filter(is_active=True)
        role = _internship_role(self.request.user)
        if role == "COMPANY":
            company = _company_for_user(self.request.user)
            if not company:
                return InternshipPosition.objects.none()
            queryset = queryset.filter(company=company)

        return queryset.annotate(
            accepted_applications=Count(
                "applications",
                filter=Q(applications__student_decision="ACCEPTED"),
                distinct=True,
            )
        )

    def perform_create(self, serializer):
        company = _company_for_user(self.request.user)
        role = _internship_role(self.request.user)
        if not company:
            # If the authenticated user has a Company role, allow creation by
            # creating a minimal Company record and linking the user as mentor.
            if role == "COMPANY":
                company_name = (
                    getattr(self.request.user, "company_name", None)
                    or getattr(self.request.user, "company", None)
                    or self.request.user.email
                )
                company = Company.objects.create(
                    contact_email=self.request.user.email,
                    company_name=company_name,
                    is_active=True,
                )
                try:
                    CompanyMentor.objects.create(user=self.request.user, company=company)
                except Exception:
                    # Ignore mentor creation errors (e.g., unique constraint); proceed with company
                    pass
            else:
                raise PermissionDenied("Only company users can create internships")

        position = serializer.save(company=company)

        from core.services.audit_service import log_audit_event

        log_audit_event(
            actor=self.request.user,
            action="INTERNSHIP_POSITION_CREATED",
            target_type="InternshipPosition",
            target_id=position.id,
            description=f"Position '{position.title}' created for {company.company_name}.",
        )


class CompanyUserInternshipListCreateView(InternshipListCreateView):
    def get_queryset(self):
        _require_company_user_id(self.request.user, self.kwargs["user_id"])
        return super().get_queryset()

    def post(self, request, *args, **kwargs):
        _require_company_user_id(request.user, kwargs["user_id"])

        internship_id = request.data.get("internship_id")
        if internship_id:
            position = get_object_or_404(InternshipPosition, pk=internship_id)
            company = _company_for_user(request.user)
            if not company or position.company_id != company.id:
                raise PermissionDenied("You can only view applicants for your own internships.")

            queryset = InternshipApplication.objects.filter(position=position)
            dept_status = request.data.get("dept_status")
            mentor_status = request.data.get("mentor_status")
            student_decision = request.data.get("student_decision")

            if dept_status:
                queryset = queryset.filter(dept_status=str(dept_status).strip().upper())
            if mentor_status:
                queryset = queryset.filter(mentor_status=str(mentor_status).strip().upper())
            if student_decision:
                queryset = queryset.filter(student_decision=str(student_decision).strip().upper())

            serializer = CompanyApplicationSerializer(queryset, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        return super().post(request, *args, **kwargs)

    def perform_create(self, serializer):
        _require_company_user_id(self.request.user, self.kwargs["user_id"])
        return super().perform_create(serializer)


class CompanyUserInternshipRetrieveUpdateView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = InternshipPositionSerializer
    permission_classes = [IsAuthenticated]
    queryset = InternshipPosition.objects.all()

    def get_queryset(self):
        _require_company_user_id(self.request.user, self.kwargs["user_id"])
        company = _company_for_user(self.request.user)
        if not company:
            return InternshipPosition.objects.none()
        return InternshipPosition.objects.filter(company=company)

    def perform_update(self, serializer):
        _require_company_user_id(self.request.user, self.kwargs["user_id"])
        company = _company_for_user(self.request.user)
        if not company:
            raise PermissionDenied("Only company users can update internship positions")

        if serializer.instance.company != company:
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

    def perform_destroy(self, instance):
        _require_company_user_id(self.request.user, self.kwargs["user_id"])
        company = _company_for_user(self.request.user)
        if not company:
            raise PermissionDenied("Only company users can delete internship positions")

        if instance.company != company:
            raise PermissionDenied("You cannot delete internships from another company")

        from core.services.audit_service import log_audit_event

        log_audit_event(
            actor=self.request.user,
            action="INTERNSHIP_POSITION_DELETED",
            target_type="InternshipPosition",
            target_id=instance.id,
            description=f"Position '{instance.title}' deleted by {self.request.user.email}.",
        )
        instance.delete()


class InternshipRetrieveUpdateView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = InternshipPositionSerializer
    permission_classes = [IsAuthenticated]
    queryset = InternshipPosition.objects.all()

    def perform_update(self, serializer):
        company = _company_for_user(self.request.user)
        if not company:
            raise PermissionDenied("Only company users can update internship positions")

        if serializer.instance.company != company:
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

    def perform_destroy(self, instance):
        company = _company_for_user(self.request.user)
        if not company:
            raise PermissionDenied("Only company users can delete internship positions")

        if instance.company != company:
            raise PermissionDenied("You cannot delete internships from another company")

        from core.services.audit_service import log_audit_event

        log_audit_event(
            actor=self.request.user,
            action="INTERNSHIP_POSITION_DELETED",
            target_type="InternshipPosition",
            target_id=instance.id,
            description=f"Position '{instance.title}' deleted by {self.request.user.email}.",
        )
        instance.delete()


class AvailableInternshipPositionListView(generics.ListAPIView):
    serializer_class = InternshipPositionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = InternshipPosition.objects.filter(is_active=True)
        role = _internship_role(self.request.user)
        if role == "COMPANY":
            mentor = CompanyMentor.objects.filter(user=self.request.user).first()
            if not mentor:
                return InternshipPosition.objects.none()
            queryset = queryset.filter(company=mentor.company)

        return (
            queryset
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
            company = _company_for_user(user)
            if not company:
                return base_qs.none()
            return base_qs.filter(company=company)

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


class CoordinatorPendingApplicationsListView(generics.ListAPIView):
    """GET /applications/ — pending applications for the coordinator's department."""

    serializer_class = InternshipRequestFormSerializer
    permission_classes = [IsAuthenticated, IsCoordinatorUser]

    def get_queryset(self):
        user = self.request.user
        coordinator = getattr(user, "staff", None)
        if not coordinator:
            return InternshipApplication.objects.none()

        return (
            InternshipApplication.objects.filter(
                student__department=coordinator.department,
                dept_status=InternshipApplication.DeptStatus.PENDING,
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

    def list(self, request, *args, **kwargs):
        applications = self.get_queryset()
        application_data = self.get_serializer(applications, many=True).data

        user = request.user
        coordinator = getattr(user, "staff", None)
        self_placements = []
        if coordinator:
            self_placements = SelfPlacementRequest.objects.filter(
                student__department=coordinator.department,
                status=SelfPlacementRequest.Status.PENDING,
            ).select_related("student__user", "student__department", "student__advisor__user")

        self_placement_data = [_self_placement_to_application_like(obj) for obj in self_placements]
        combined = application_data + self_placement_data
        combined.sort(key=lambda item: item.get("created_at") or "", reverse=True)
        return Response(combined, status=status.HTTP_200_OK)


class CoordinatorApprovedApplicationsListView(generics.ListAPIView):
    """GET /applications/approved/ — applications that have been approved by the department and are visible to coordinators."""

    serializer_class = InternshipRequestFormSerializer
    permission_classes = [IsAuthenticated, IsCoordinatorUser]

    def get_queryset(self):
        user = self.request.user
        coordinator = getattr(user, "staff", None)
        if not coordinator:
            return InternshipApplication.objects.none()

        return (
            InternshipApplication.objects.filter(
                student__department=coordinator.department,
                dept_status=InternshipApplication.DeptStatus.APPROVED,
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

    def list(self, request, *args, **kwargs):
        applications = self.get_queryset()
        application_data = self.get_serializer(applications, many=True).data

        user = request.user
        coordinator = getattr(user, "staff", None)
        self_placements = []
        if coordinator:
            self_placements = SelfPlacementRequest.objects.filter(
                student__department=coordinator.department,
                status=SelfPlacementRequest.Status.APPROVED,
            ).select_related("student__user", "student__department", "student__advisor__user")

        self_placement_data = [_self_placement_to_application_like(obj) for obj in self_placements]
        combined = application_data + self_placement_data
        combined.sort(key=lambda item: item.get("created_at") or "", reverse=True)

        app_ids = [item["id"] for item in combined if item.get("id")]
        from core.models import AdvisorAssignment
        examiner_assignments = (
            AdvisorAssignment.objects.filter(
                internship_id__in=app_ids,
                role="EXAMINER",
            )
            .select_related("advisor")
            .order_by("internship_id", "id")
        )

        examiner_map = {}
        for assignment in examiner_assignments:
            iid = assignment.internship_id
            name = assignment.advisor.get_full_name() or assignment.advisor.username
            if iid not in examiner_map:
                examiner_map[iid] = []
            examiner_map[iid].append(name)

        for item in combined:
            iid = item.get("id")
            names = examiner_map.get(iid, [])
            item["examiner_name"] = names[0] if len(names) > 0 else item.get("examiner_name", "")
            item["examiner2_name"] = names[1] if len(names) > 1 else item.get("examiner2_name", "")

        return Response(combined, status=status.HTTP_200_OK)


class ApplicationDetailView(generics.RetrieveAPIView):
    """GET /applications/<pk>/ — return a single application if requester is authorized.

    Allowed viewers:
      - The student who owns the application
      - A coordinator for the student's department
      - An advisor assigned to the application
      - A company mentor for the position's company
    """
    serializer_class = InternshipRequestFormSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            InternshipApplication.objects.select_related(
                "student__user",
                "student__department",
                "position",
                "position__company",
                "advisor__user",
                "mentor__user",
            )
        )

    def get_object(self):
        obj = super().get_object()
        user = self.request.user

        def _return_synced():
            _sync_application_advisor_status_from_final_eval(obj)
            return obj

        # student owner
        if getattr(user, "student_profile", None) and obj.student == user.student_profile:
            return _return_synced()

        # coordinator of same department
        coord = getattr(user, "staff", None)
        if coord and coord.department_id == obj.student.department_id:
            return _return_synced()

        # advisor assigned
        if getattr(user, "advisor_profile", None) and obj.advisor and obj.advisor.user_id == user.id:
            return _return_synced()

        # company mentor
        if getattr(user, "company_mentorships", None):
            if obj.position and obj.position.company_id:
                mentor_exists = obj.position.company.mentor and obj.position.company.mentor.user_id == user.id
                if mentor_exists:
                    return _return_synced()

        raise PermissionDenied("Not authorized to view this application")
