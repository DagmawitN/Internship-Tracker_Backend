from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.evaluation_validators import (
    validate_advisor_assignment,
    validate_examiner_assignment,
)
from core.models import Report, ReportFile, ReportReviewStatus
from core.permissions import IsAdvisorUser, IsExaminerUser
from core.serializers.report_serializers import (
    AdvisorFinalReportCommentSerializer,
    FinalReportDetailSerializer,
)
from core.services.evaluation_workflow import (
    advisor_internship_queryset,
    examiner_internship_queryset,
)


def _final_report_queryset_for_examiner(user):
    internship_ids = examiner_internship_queryset(user).values_list("pk", flat=True)
    return (
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


def _final_report_queryset_for_advisor(user):
    internship_ids = advisor_internship_queryset(user).values_list("pk", flat=True)
    return (
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


class ExaminerFinalReportListAPIView(APIView):
    """GET /api/examiner/final-reports/ — list student final reports for assigned internships."""

    permission_classes = [IsAuthenticated, IsExaminerUser]

    def get(self, request):
        reports = _final_report_queryset_for_examiner(request.user)
        return Response(
            FinalReportDetailSerializer(reports, many=True).data,
            status=status.HTTP_200_OK,
        )


class ExaminerFinalReportDetailAPIView(APIView):
    """GET /api/examiner/final-reports/<report_id>/"""

    permission_classes = [IsAuthenticated, IsExaminerUser]

    def get(self, request, report_id):
        report = get_object_or_404(
            _final_report_queryset_for_examiner(request.user),
            pk=report_id,
        )
        return Response(
            FinalReportDetailSerializer(report).data,
            status=status.HTTP_200_OK,
        )


class ExaminerFinalReportDownloadAPIView(APIView):
    """GET /api/examiner/final-reports/<report_id>/download/"""

    permission_classes = [IsAuthenticated, IsExaminerUser]

    def get(self, request, report_id):
        report = get_object_or_404(
            _final_report_queryset_for_examiner(request.user),
            pk=report_id,
        )
        report_file = ReportFile.objects.filter(report=report).first()
        if not report_file or not report_file.file:
            return Response(
                {"detail": "Report file not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return FileResponse(
            open(report_file.file.path, "rb"),
            as_attachment=True,
            filename=report_file.file_name,
        )


class ExaminerFinalReportApproveAPIView(APIView):
    """PATCH /api/examiner/final-reports/<report_id>/approve/"""

    permission_classes = [IsAuthenticated, IsExaminerUser]

    def patch(self, request, report_id):
        report = get_object_or_404(
            Report.objects.select_related("internship"),
            pk=report_id,
            report_type="FINAL",
        )
        try:
            validate_examiner_assignment(request.user, report.internship)
        except DjangoValidationError as exc:
            return Response(exc.message_dict, status=status.HTTP_403_FORBIDDEN)

        if report.status not in (
            ReportReviewStatus.SUBMITTED,
            "",
        ):
            return Response(
                {"detail": "Only submitted final reports can be approved by examiner."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        report.status = ReportReviewStatus.EXAMINER_APPROVED
        report.examiner_reviewer = request.user
        report.examiner_approved_at = timezone.now()
        report.examiner_rejected_at = None
        report.save()

        return Response(
            {
                "message": "Final report approved by examiner.",
                "report": FinalReportDetailSerializer(report).data,
            },
            status=status.HTTP_200_OK,
        )


class ExaminerFinalReportRejectAPIView(APIView):
    """PATCH /api/examiner/final-reports/<report_id>/reject/"""

    permission_classes = [IsAuthenticated, IsExaminerUser]

    def patch(self, request, report_id):
        report = get_object_or_404(
            Report.objects.select_related("internship"),
            pk=report_id,
            report_type="FINAL",
        )
        try:
            validate_examiner_assignment(request.user, report.internship)
        except DjangoValidationError as exc:
            return Response(exc.message_dict, status=status.HTTP_403_FORBIDDEN)

        if report.status not in (
            ReportReviewStatus.SUBMITTED,
            "",
        ):
            return Response(
                {"detail": "Only submitted final reports can be rejected by examiner."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        report.status = ReportReviewStatus.EXAMINER_REJECTED
        report.examiner_reviewer = request.user
        report.examiner_rejected_at = timezone.now()
        report.examiner_approved_at = None
        report.save()

        return Response(
            {
                "message": "Final report rejected by examiner.",
                "report": FinalReportDetailSerializer(report).data,
            },
            status=status.HTTP_200_OK,
        )


class AdvisorFinalReportCommentAPIView(APIView):
    """PATCH /api/advisor/final-reports/<report_id>/comment/"""

    permission_classes = [IsAuthenticated, IsAdvisorUser]

    def patch(self, request, report_id):
        report = get_object_or_404(
            Report.objects.select_related("internship"),
            pk=report_id,
            report_type="FINAL",
        )
        try:
            validate_advisor_assignment(request.user, report.internship)
        except DjangoValidationError as exc:
            return Response(exc.message_dict, status=status.HTTP_403_FORBIDDEN)

        body = AdvisorFinalReportCommentSerializer(data=request.data)
        body.is_valid(raise_exception=True)

        report.advisor_comment = body.validated_data["comment"]
        report.advisor_comment_by = request.user
        report.advisor_comment_at = timezone.now()
        report.save(update_fields=["advisor_comment", "advisor_comment_by", "advisor_comment_at"])

        return Response(
            {
                "message": "Advisor comment saved.",
                "report": FinalReportDetailSerializer(report).data,
            },
            status=status.HTTP_200_OK,
        )
