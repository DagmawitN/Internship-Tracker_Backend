from django.db import models
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import (
    AdvisorAssignment,
    DailyLogEntry,
    InternshipApplication,
    Report,
    ReportFeedback,
    ReportFile,
    ReportReviewStatus,
    Student,
    WeeklyLogbook,
)
from core.services.evaluation_workflow import advisor_internship_queryset
from core.serializers.report_serializers import (
    AdvisorFinalReportListSerializer,
    StudentInternshipDocumentSerializer,
    AdvisorWeeklyLogbookSerializer,
    DailyLogEntrySerializer,
    SubmitFinalReportSerializer,
    WeeklyLogbookSerializer,
)
from core.services.notification_service import create_notification
from core.permissions import IsAdvisorUser, IsExaminerUser


class StudentInternshipDocumentListCreateAPIView(APIView):
    """GET/POST /documents/my/ for student internship supporting documents."""

    permission_classes = [IsAuthenticated]

    def _get_active_internship(self, student, internship_id=None):
        qs = InternshipApplication.objects.filter(student=student).filter(
            models.Q(student_decision="ACCEPTED") | models.Q(dept_status="APPROVED")
        )
        if internship_id:
            qs = qs.filter(pk=internship_id)
        return qs.order_by("-created_at").first()

    def get(self, request):
        if not hasattr(request.user, "student_profile"):
            return Response(
                {"error": "Only students can access this endpoint."},
                status=status.HTTP_403_FORBIDDEN,
            )

        student = request.user.student_profile
        internship_id = request.query_params.get("internship_id")
        internship = self._get_active_internship(student, internship_id)
        if not internship:
            return Response([], status=status.HTTP_200_OK)

        docs = (
            Report.objects.filter(internship=internship, report_type="OTHER")
            .prefetch_related("files", "feedbacks")
            .order_by("-submission_date")
        )
        serializer = StudentInternshipDocumentSerializer(docs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        if not hasattr(request.user, "student_profile"):
            return Response(
                {"error": "Only students can upload internship documents."},
                status=status.HTTP_403_FORBIDDEN,
            )

        student = request.user.student_profile
        internship_id = request.data.get("internship_id")
        internship = self._get_active_internship(student, internship_id)
        if not internship:
            return Response(
                {"error": "No active internship application found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response(
                {"error": "file is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        title = (request.data.get("title") or file_obj.name or "Internship document").strip()
        description = (request.data.get("description") or "").strip()

        report = Report.objects.create(
            internship=internship,
            report_type="OTHER",
            title=title,
            status=ReportReviewStatus.SUBMITTED,
            submission_date=timezone.now(),
        )

        ReportFile.objects.create(
            report=report,
            file=file_obj,
            file_name=file_obj.name,
            file_size=file_obj.size,
            mime_type=getattr(file_obj, "content_type", "") or "",
        )

        if description:
            ReportFeedback.objects.create(report=report, feedback_text=description)

        serializer = StudentInternshipDocumentSerializer(report)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdvisorInternshipDocumentListAPIView(APIView):
    """GET /documents/advisor/ for advisor-facing student internship documents."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        internship_ids = list(
            AdvisorAssignment.objects.filter(advisor=request.user, role="ADVISOR")
            .values_list("internship_id", flat=True)
            .distinct()
        )
        if not internship_ids:
            internship_ids = list(
                advisor_internship_queryset(request.user).values_list("id", flat=True)
            )

        internship_id = request.query_params.get("internship_id")
        if internship_id:
            internship_ids = [iid for iid in internship_ids if str(iid) == str(internship_id)]

        if not internship_ids:
            return Response([], status=status.HTTP_200_OK)

        docs = (
            Report.objects.filter(internship_id__in=internship_ids, report_type="OTHER")
            .select_related(
                "internship__student__user",
                "internship__student__advisor__user",
                "internship__position__company",
            )
            .prefetch_related("files", "feedbacks")
            .order_by("-submission_date")
        )

        serializer = StudentInternshipDocumentSerializer(docs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ExaminerInternshipDocumentListAPIView(APIView):
    """GET /documents/examiner/ for examiner-facing student internship documents."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        internship_ids = list(
            AdvisorAssignment.objects.filter(advisor=request.user, role="EXAMINER")
            .values_list("internship_id", flat=True)
            .distinct()
        )

        internship_id = request.query_params.get("internship_id")
        if internship_id:
            internship_ids = [iid for iid in internship_ids if str(iid) == str(internship_id)]

        if not internship_ids:
            return Response([], status=status.HTTP_200_OK)

        docs = (
            Report.objects.filter(internship_id__in=internship_ids, report_type="OTHER")
            .select_related(
                "internship__student__user",
                "internship__student__advisor__user",
                "internship__position__company",
            )
            .prefetch_related("files", "feedbacks")
            .order_by("-submission_date")
        )

        serializer = StudentInternshipDocumentSerializer(docs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ReportAdvisorReviewAPIView(APIView):
    """POST /documents/{pk}/advisor-review/ -- advisor approves/rejects a student's uploaded document"""

    permission_classes = [IsAuthenticated, IsAdvisorUser]

    def post(self, request, pk):
        report = get_object_or_404(Report, pk=pk)
        application = report.internship

        # Ensure the advisor is assigned to this student
        advisor_profile = getattr(application.student, "advisor", None)
        if not advisor_profile or not advisor_profile.user or advisor_profile.user.id != request.user.id:
            return Response({"error": "You are not the assigned advisor for this student."}, status=status.HTTP_403_FORBIDDEN)

        action = str(request.data.get("action", "")).lower()
        comment = request.data.get("comment", "") or ""

        if action not in ("approve", "reject"):
            return Response({"error": "action must be 'approve' or 'reject'"}, status=status.HTTP_400_BAD_REQUEST)

        if action == "approve":
            report.status = ReportReviewStatus.ADVISOR_APPROVED
            report.approved_at = timezone.now()
        else:
            report.status = ReportReviewStatus.REJECTED
            report.rejected_at = timezone.now()

        if comment:
            report.advisor_comment = comment
            report.advisor_comment_by = request.user
            report.advisor_comment_at = timezone.now()

        report.reviewed_by = request.user
        report.reviewed_at = timezone.now()
        report.save()

        # Notify student of decision
        try:
            create_notification(
                recipient=application.student.user,
                title="Advisor Document Review",
                message=(f"Your document '{report.title}' was {'approved' if action == 'approve' else 'rejected'} by your advisor."),
                notification_type="DOCUMENT_REVIEW",
                related_object_id=report.id,
                related_object_type="Report",
            )
        except Exception:
            pass

        serializer = StudentInternshipDocumentSerializer(report)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ReportExaminerReviewAPIView(APIView):
    """POST /documents/{pk}/examiner-review/ -- examiner approves/rejects a student's uploaded document"""

    permission_classes = [IsAuthenticated, IsExaminerUser]

    def post(self, request, pk):
        report = get_object_or_404(Report, pk=pk)
        application = report.internship

        # Ensure examiner assignment exists for this internship and user
        from core.models import AdvisorAssignment

        assignment_exists = AdvisorAssignment.objects.filter(
            internship=application,
            role="EXAMINER",
            advisor=request.user,
        ).exists()

        if not assignment_exists:
            return Response({"error": "You are not assigned as examiner for this internship."}, status=status.HTTP_403_FORBIDDEN)

        action = str(request.data.get("action", "")).lower()
        comment = request.data.get("comment", "") or ""

        if action not in ("approve", "reject"):
            return Response({"error": "action must be 'approve' or 'reject'"}, status=status.HTTP_400_BAD_REQUEST)

        if action == "approve":
            report.status = ReportReviewStatus.EXAMINER_APPROVED
            report.examiner_approved_at = timezone.now()
            report.examiner_reviewer = request.user
        else:
            report.status = ReportReviewStatus.EXAMINER_REJECTED
            report.examiner_rejected_at = timezone.now()
            report.examiner_reviewer = request.user

        if comment:
            # store comment in advisor_comment for now (no dedicated field for examiner in OTHER docs)
            report.advisor_comment = report.advisor_comment or ""
            # prefer creating a ReportFeedback record for examiner comments
            ReportFeedback.objects.create(report=report, feedback_text=comment)

        report.reviewed_by = request.user
        report.reviewed_at = timezone.now()
        report.save()

        # Notify student
        try:
            create_notification(
                recipient=application.student.user,
                title="Examiner Document Review",
                message=(f"Your document '{report.title}' was {'approved' if action == 'approve' else 'rejected'} by the internal examiner."),
                notification_type="DOCUMENT_REVIEW",
                related_object_id=report.id,
                related_object_type="Report",
            )
        except Exception:
            pass

        serializer = StudentInternshipDocumentSerializer(report)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AddDailyLogEntryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, logbook_id):

        try:
            logbook = WeeklyLogbook.objects.get(id=logbook_id)

        except WeeklyLogbook.DoesNotExist:
            return Response(
                {"error": "Logbook not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if logbook.status != "DRAFT":
            return Response(
                {"error": "Cannot edit submitted logbook."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = DailyLogEntrySerializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        serializer.save(weekly_logbook=logbook)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CreateWeeklyLogbookAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        student_id = request.query_params.get("student_id")
        internship_id = request.query_params.get("internship_id")

        if request.user.is_authenticated and hasattr(request.user, "student_profile"):
            student = request.user.student_profile
        else:
            student = None

        # Allow coordinators and advisors to inspect any student logbooks,
        # but keep access scoped to the authenticated coordinator's department.
        is_coordinator = bool(getattr(getattr(request.user, "role", None), "role_name", "") == "COORDINATOR")
        is_advisor = bool(getattr(getattr(request.user, "role", None), "role_name", "") == "ADVISOR")
        if not student and not (is_coordinator or is_advisor):
            return Response(
                {"error": "Only students, advisors, and coordinators can access logbooks."},
                status=status.HTTP_403_FORBIDDEN,
            )

        qs = WeeklyLogbook.objects.select_related(
            "internship__student__user",
            "internship__position__company",
        ).prefetch_related("daily_entries")

        if student_id:
            student_qs = Student.objects.filter(models.Q(student_id=str(student_id)) | models.Q(pk=student_id))
            target_student = student_qs.select_related("department", "user").first()
            if not target_student:
                return Response([], status=status.HTTP_200_OK)

            if is_coordinator:
                staff = getattr(request.user, "staff", None)
                if staff and target_student.department_id != staff.department_id:
                    return Response(
                        {"detail": "Not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

            qs = qs.filter(internship__student=target_student)
        elif student:
            qs = qs.filter(internship__student=student)
        else:
            return Response(
                {"error": "student_id query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if internship_id:
            qs = qs.filter(internship_id=internship_id)

        qs = qs.order_by("week_number")
        serializer = WeeklyLogbookSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):

        if not hasattr(request.user, "student_profile"):
            return Response(
                {"error": "Only students can create logbooks."},
                status=status.HTTP_403_FORBIDDEN,
            )

        week_number = request.data.get("week_number")
        if not week_number:
            return Response(
                {"error": "week_number is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        student = request.user.student_profile

        # Allow caller to pass the application id directly (avoids ambiguity)
        internship_id = request.data.get("internship_id") or request.data.get("application_id")

        if internship_id:
            internship = InternshipApplication.objects.filter(
                pk=internship_id, student=student
            ).first()
        else:
            # Fall back: find the most recent approved/accepted application
            internship = InternshipApplication.objects.filter(
                student=student,
            ).filter(
                models.Q(student_decision="ACCEPTED") | models.Q(dept_status="APPROVED")
            ).order_by("-created_at").first()

        if not internship:
            return Response(
                {"error": "No active internship application found. Pass internship_id if needed."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get or create — idempotent so duplicate calls are safe
        logbook, created = WeeklyLogbook.objects.get_or_create(
            internship=internship,
            week_number=week_number,
        )

        serializer = WeeklyLogbookSerializer(logbook)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class SubmitFinalReportAPIView(APIView):
    """
    API endpoint for authenticated students to submit and download their final internship report.
    POST: Submit final report with file upload.
    GET: Download the submitted final report.
    """

    permission_classes = [IsAuthenticated]

    def _has_permission(self, user, student):
        """
        Check if user has permission to access the student's final report.
        """
        # Student can access their own report
        if hasattr(user, "student_profile") and user.student_profile == student:
            return True

        # Advisors, coordinators, examiners can access assigned students
        if AdvisorAssignment.objects.filter(
            models.Q(coordinator=user) | models.Q(advisor=user), student=student
        ).exists():
            return True

        # Staff members in the same department can access
        if hasattr(user, "staff") and user.staff.department == student.department:
            return True

        return False

    def post(self, request, student_id):
        # Check if user is a student
        if not hasattr(request.user, "student_profile"):
            return Response(
                {"error": "Only students can submit final reports."},
                status=status.HTTP_403_FORBIDDEN,
            )

        student = request.user.student_profile

        # Ensure student can only submit their own report
        if student.id != student_id:
            return Response(
                {"error": "Students can only submit their own reports."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Find student's active or accepted internship application
        internship = InternshipApplication.objects.filter(
            student=student,
            student_decision="ACCEPTED",
        ).first()

        if not internship:
            return Response(
                {"error": "No accepted internship application found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if FINAL report already submitted
        if Report.objects.filter(internship=internship, report_type="FINAL").exists():
            return Response(
                {"error": "Final report already submitted for this internship."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate and create report
        serializer = SubmitFinalReportSerializer(data=request.data)
        if serializer.is_valid():
            report = serializer.save(
                internship=internship,
                report_type="FINAL",
                status=ReportReviewStatus.SUBMITTED,
                submission_date=timezone.now(),
            )

            # Notify advisor that a report has been submitted
            student_user = request.user
            student_name = student_user.get_full_name() or student_user.username
            advisor = getattr(internship.student, "advisor", None)
            if advisor:
                create_notification(
                    recipient=advisor.user,
                    title="New Report Submitted",
                    message=f"{student_name} submitted a final internship report.",
                    notification_type="REPORT_SUBMITTED",
                    related_object_id=report.id,
                    related_object_type="Report",
                )

            return Response(
                {
                    "message": "Final report submitted successfully",
                    "report_id": report.id,
                    "status": "SUBMITTED",
                },
                status=status.HTTP_201_CREATED,
            )
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request, student_id):
        """
        API endpoint for authenticated users to download a student's final internship report.
        """
        # Get the student
        student = get_object_or_404(Student, id=student_id)

        # Check permissions
        if not self._has_permission(request.user, student):
            return Response(
                {"error": "You do not have permission to view this report."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Find student's accepted internship application
        internship = InternshipApplication.objects.filter(
            student=student,
            student_decision="ACCEPTED",
        ).first()

        if not internship:
            return Response(
                {"error": "No accepted internship application found for this student."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Find the FINAL report
        try:
            report = Report.objects.get(internship=internship, report_type="FINAL")
        except Report.DoesNotExist:
            return Response(
                {"error": "Final report not found."}, status=status.HTTP_404_NOT_FOUND
            )

        # Get the report file
        try:
            report_file = ReportFile.objects.get(report=report)
        except ReportFile.DoesNotExist:
            return Response(
                {"error": "Report file not found."}, status=status.HTTP_404_NOT_FOUND
            )

        # Return the file as download
        file_path = report_file.file.path
        response = FileResponse(
            open(file_path, "rb"), as_attachment=True, filename=report_file.file_name
        )
        return response


class AdvisorFinalReportListAPIView(APIView):
    """
    API endpoint for advisors to view FINAL internship reports
    submitted by students assigned to them (includes examiner status and comments).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Check if user has Advisor role
        if not hasattr(request.user, "role") or request.user.role.role_name != "ADVISOR":
            return Response(
                {"error": "Only advisors can access this endpoint."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get internships assigned to this advisor
        assigned_internships = AdvisorAssignment.objects.filter(
            advisor=request.user
        ).values_list("internship", flat=True)

        # Get FINAL reports for those internships
        reports = (
            Report.objects.filter(
                report_type="FINAL", internship__in=assigned_internships
            )
            .select_related(
                "internship__student__user", "internship__position__company"
            )
            .prefetch_related("files")
            .order_by("-submission_date")
        )
        internship_ids = advisor_internship_queryset(request.user).values_list(
            "pk", flat=True
        )
        reports = (
            Report.objects.filter(report_type="FINAL", internship_id__in=internship_ids)
            .select_related(
                "internship__student__user",
                "internship__position__company",
                "examiner_reviewer",
                "advisor_comment_by",
            )
            .prefetch_related("files")
            .order_by("-submission_date")
        )

        serializer = AdvisorFinalReportListSerializer(reports, many=True)
        return Response(serializer.data)


class AdvisorWeeklyLogbookListAPIView(APIView):
    """
    API endpoint for advisors to view weekly logbooks submitted by students
    assigned to them.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from core.models import Advisor
        # Allow access if user has ADVISOR role, an AdvisorAssignment, or an Advisor profile
        has_advisor_role = (
            hasattr(request.user, "role")
            and request.user.role
            and request.user.role.role_name == "ADVISOR"
        )
        advisor_profile = Advisor.objects.filter(user=request.user).first()
        has_advisor_assignment = AdvisorAssignment.objects.filter(advisor=request.user).exists()

        if not (has_advisor_role or advisor_profile or has_advisor_assignment):
            return Response(
                {"error": "Only advisors can access this endpoint."},
                status=status.HTTP_403_FORBIDDEN,
            )

        internship_id = request.query_params.get("internship_id")

        # Build the set of internship application IDs this advisor can see:
        # Path 1 — via AdvisorAssignment table (role=ADVISOR)
        assignment_ids = AdvisorAssignment.objects.filter(
            advisor=request.user, role="ADVISOR"
        ).values_list("internship_id", flat=True)

        # Path 2 — via Student.advisor FK (the coordinator assigns advisor to student)
        student_ids = []
        if advisor_profile:
            # M2M assigned_students
            m2m_ids = list(advisor_profile.assigned_students.values_list("id", flat=True))
            # FK: InternshipApplication.student.advisor = advisor_profile
            fk_ids = list(
                InternshipApplication.objects.filter(
                    student__advisor=advisor_profile
                ).values_list("student_id", flat=True)
            )
            student_ids = list(set(m2m_ids) | set(fk_ids))

        # Combine both paths
        qs = WeeklyLogbook.objects.filter(
            models.Q(internship_id__in=assignment_ids) |
            models.Q(internship__student_id__in=student_ids)
        ).select_related(
            "internship__student__user",
            "internship__position__company",
        ).prefetch_related("daily_entries")

        if internship_id:
            qs = qs.filter(internship_id=internship_id)

        qs = qs.order_by("internship_id", "week_number")

        serializer = AdvisorWeeklyLogbookSerializer(qs, many=True)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# Student: list own logbooks
# ---------------------------------------------------------------------------

class StudentWeeklyLogbookListAPIView(APIView):
    """GET /logbooks/my/ — returns all weekly logbooks for the authenticated student."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not hasattr(request.user, "student_profile"):
            return Response({"error": "Only students can access this endpoint."}, status=status.HTTP_403_FORBIDDEN)

        student = request.user.student_profile
        internship_id = request.query_params.get("internship_id")
        internship_qs = InternshipApplication.objects.filter(student=student).filter(
            models.Q(student_decision="ACCEPTED") | models.Q(dept_status="APPROVED")
        )
        if internship_id:
            internship_qs = internship_qs.filter(pk=internship_id)

        internship = internship_qs.order_by("-created_at").first()

        if not internship:
            return Response([], status=status.HTTP_200_OK)

        logbooks = (
            WeeklyLogbook.objects.filter(internship=internship)
            .select_related(
                "internship__student__user",
                "internship__position__company",
            )
            .prefetch_related("daily_entries")
            .order_by("week_number")
        )
        serializer = AdvisorWeeklyLogbookSerializer(logbooks, many=True)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# Student: submit a logbook week (DRAFT → SUBMITTED)
# ---------------------------------------------------------------------------

class SubmitWeeklyLogbookAPIView(APIView):
    """POST /logbooks/<id>/submit/
    Student submits a draft logbook week for company review.
    Body (optional): { "student_comment": "..." }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, logbook_id):
        if not hasattr(request.user, "student_profile"):
            return Response({"error": "Only students can submit logbooks."}, status=status.HTTP_403_FORBIDDEN)

        logbook = get_object_or_404(WeeklyLogbook, pk=logbook_id)

        # Ownership check
        if logbook.internship.student != request.user.student_profile:
            return Response({"error": "You can only submit your own logbook."}, status=status.HTTP_403_FORBIDDEN)

        if logbook.status not in (WeeklyLogbook.Status.DRAFT, WeeklyLogbook.Status.SUBMITTED):
            return Response(
                {"error": f"Cannot submit a logbook with status '{logbook.status}'. Only DRAFT or SUBMITTED logbooks can be (re)submitted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        logbook.status = WeeklyLogbook.Status.SUBMITTED
        logbook.student_comment = request.data.get("student_comment", logbook.student_comment)
        logbook.submitted_at = timezone.now()
        logbook.save(update_fields=["status", "student_comment", "submitted_at"])

        # Notify company mentor if assigned
        mentor = getattr(logbook.internship, "mentor", None)
        if mentor:
            create_notification(
                recipient=mentor.user,
                title="Logbook Week Submitted",
                message=(
                    f"{request.user.get_full_name() or request.user.username} submitted "
                    f"Week {logbook.week_number} of their internship logbook for your review."
                ),
                notification_type="LOGBOOK_SUBMITTED",
                related_object_id=logbook.id,
                related_object_type="WeeklyLogbook",
            )

        return Response(WeeklyLogbookSerializer(logbook).data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Company: verify a submitted logbook (SUBMITTED → VERIFIED)
# ---------------------------------------------------------------------------

class VerifyWeeklyLogbookAPIView(APIView):
    """POST /logbooks/<id>/verify/
    Company mentor verifies (approves) or rejects a submitted logbook week.
    Body: { "action": "approve" | "reject", "comment": "..." }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, logbook_id):
        from core.models import CompanyMentor
        logbook = get_object_or_404(WeeklyLogbook, pk=logbook_id)

        # Must be the company mentor for this internship's company
        try:
            mentor = CompanyMentor.objects.get(user=request.user)
        except CompanyMentor.DoesNotExist:
            return Response({"error": "Only company mentors can verify logbooks."}, status=status.HTTP_403_FORBIDDEN)

        if logbook.internship.position.company != mentor.company:
            return Response({"error": "You can only verify logbooks for your company."}, status=status.HTTP_403_FORBIDDEN)

        if logbook.status != WeeklyLogbook.Status.SUBMITTED:
            return Response(
                {"error": f"Cannot verify a logbook with status '{logbook.status}'. Only SUBMITTED logbooks can be verified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        action = request.data.get("action", "").lower()
        comment = request.data.get("comment", "")

        if action not in ("approve", "reject"):
            return Response({"error": "action must be 'approve' or 'reject'."}, status=status.HTTP_400_BAD_REQUEST)

        logbook.company_comment = comment
        logbook.verified_by = mentor
        logbook.verified_at = timezone.now()

        if action == "approve":
            logbook.status = WeeklyLogbook.Status.VERIFIED
        else:
            # Reject sends it back to DRAFT so student can revise
            logbook.status = WeeklyLogbook.Status.DRAFT
            logbook.submitted_at = None

        logbook.save(update_fields=["status", "company_comment", "verified_by", "verified_at", "submitted_at"])

        # Notify student
        student_user = logbook.internship.student.user
        if action == "approve":
            create_notification(
                recipient=student_user,
                title="Logbook Week Verified by Company",
                message=f"Week {logbook.week_number} of your logbook has been verified by your company mentor and sent to your advisor.",
                notification_type="LOGBOOK_VERIFIED",
                related_object_id=logbook.id,
                related_object_type="WeeklyLogbook",
            )
        else:
            create_notification(
                recipient=student_user,
                title="Logbook Week Returned by Company",
                message=f"Week {logbook.week_number} of your logbook was returned by your company mentor{': ' + comment if comment else '.'}",
                notification_type="LOGBOOK_REJECTED",
                related_object_id=logbook.id,
                related_object_type="WeeklyLogbook",
            )

        return Response(WeeklyLogbookSerializer(logbook).data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Advisor: review a verified logbook (VERIFIED → REVIEWED or back to DRAFT)
# ---------------------------------------------------------------------------

class ReviewWeeklyLogbookAPIView(APIView):
    """POST /logbooks/<id>/review/
    Advisor approves or rejects a company-verified logbook week.
    Body: { "action": "approve" | "reject", "comment": "..." }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, logbook_id):
        logbook = get_object_or_404(WeeklyLogbook, pk=logbook_id)

        # Must be the assigned advisor for this student
        student = logbook.internship.student
        is_advisor = AdvisorAssignment.objects.filter(
            advisor=request.user,
            internship=logbook.internship,
            role="ADVISOR",
        ).exists()
        # Also allow via Student.advisor FK
        if not is_advisor:
            from core.models import Advisor
            advisor_profile = Advisor.objects.filter(user=request.user).first()
            if advisor_profile and student.advisor == advisor_profile:
                is_advisor = True

        if not is_advisor:
            return Response({"error": "You are not the assigned advisor for this student."}, status=status.HTTP_403_FORBIDDEN)

        # Allow review from SUBMITTED or VERIFIED — advisor can review regardless of
        # whether the company verify step happened (company step is optional in some workflows)
        reviewable_statuses = (
            WeeklyLogbook.Status.SUBMITTED,
            WeeklyLogbook.Status.VERIFIED,
        )
        if logbook.status not in reviewable_statuses:
            return Response(
                {"error": f"Cannot review a logbook with status '{logbook.status}'. Logbook must be SUBMITTED or VERIFIED first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        action = request.data.get("action", "").lower()
        comment = request.data.get("comment", "")

        if action not in ("approve", "reject"):
            return Response({"error": "action must be 'approve' or 'reject'."}, status=status.HTTP_400_BAD_REQUEST)

        logbook.advisor_comment = comment
        logbook.reviewed_at = timezone.now()

        if action == "approve":
            logbook.status = WeeklyLogbook.Status.REVIEWED
        else:
            # Reject sends back to DRAFT for student to revise
            logbook.status = WeeklyLogbook.Status.DRAFT
            logbook.submitted_at = None
            logbook.verified_at = None

        logbook.save(update_fields=["status", "advisor_comment", "reviewed_at", "submitted_at", "verified_at"])

        # Notify student
        student_user = student.user
        if action == "approve":
            create_notification(
                recipient=student_user,
                title="Logbook Week Approved by Advisor",
                message=f"Week {logbook.week_number} of your logbook has been approved by your advisor.",
                notification_type="LOGBOOK_APPROVED",
                related_object_id=logbook.id,
                related_object_type="WeeklyLogbook",
            )
        else:
            create_notification(
                recipient=student_user,
                title="Logbook Week Returned by Advisor",
                message=f"Week {logbook.week_number} of your logbook was returned by your advisor{': ' + comment if comment else '.'}",
                notification_type="LOGBOOK_REJECTED",
                related_object_id=logbook.id,
                related_object_type="WeeklyLogbook",
            )

        from core.services.audit_service import log_audit_event
        log_audit_event(
            actor=request.user,
            action="LOGBOOK_REVIEWED",
            target_type="WeeklyLogbook",
            target_id=logbook.id,
            description=f"Advisor {request.user.email} {action}d Week {logbook.week_number} logbook for {student_user.email}.",
        )

        return Response(WeeklyLogbookSerializer(logbook).data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Company: list logbooks for their interns
# ---------------------------------------------------------------------------

class CompanyWeeklyLogbookListAPIView(APIView):
    """GET /logbooks/company/ — returns all weekly logbooks for interns at this company.
    Optional query param: ?internship_id=<application_id> to filter to one student.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from core.models import CompanyMentor
        try:
            mentor = CompanyMentor.objects.get(user=request.user)
        except CompanyMentor.DoesNotExist:
            return Response(
                {"error": "Only company mentors can access this endpoint."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Path 1: via InternshipApplication.position.company
        # Path 2: via InternshipApplication.mentor (company mentor directly on application)
        qs = WeeklyLogbook.objects.filter(
            models.Q(internship__position__company=mentor.company) |
            models.Q(internship__mentor=mentor)
        ).distinct().select_related(
            "internship__student__user",
            "internship__position__company",
        ).prefetch_related("daily_entries").order_by("internship_id", "week_number")

        internship_id = request.query_params.get("internship_id")
        if internship_id:
            qs = qs.filter(internship_id=internship_id)

        serializer = AdvisorWeeklyLogbookSerializer(qs, many=True)
        return Response(serializer.data)
