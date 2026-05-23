from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import (
    AdvisorEvaluation,
    CompanyEvaluationStatus,
    CompanyMentor,
    FinalIndustryEvaluation,
    MonthlyIndustryEvaluation,
    OverallInternshipEvaluation,
    Report,
    ReportReviewStatus,
)
from core.permissions import IsAdvisorUser, IsCoordinatorUser
from core.serializers.evaluation_serializers import (
    AdvisorApprovalSerializer,
    AdvisorEvaluationSerializer,
    AdvisorQueueSerializer,
    CoordinatorOverallApprovalSerializer,
    ExaminerEvaluationSerializer,
    FinalIndustryEvaluationSerializer,
    MonthlyIndustryEvaluationSerializer,
    OverallInternshipEvaluationSerializer,
)
from core.services.evaluation_documents import (
    build_advisor_queue_detail,
    build_student_evaluation_status,
)
from core.services.evaluation_workflow import (
    advisor_internship_queryset,
    build_advisor_queue_item,
    can_coordinator_finalize,
    get_or_create_overall,
)
from core.evaluation_validators import (
    validate_advisor_assignment,
    validate_internship_prerequisites_for_advisor_eval,
)


def _approve_company_evaluation(evaluation, user):
    evaluation.status = CompanyEvaluationStatus.ADVISOR_APPROVED
    evaluation.advisor_reviewer = user
    evaluation.advisor_approved_at = timezone.now()
    evaluation.advisor_rejected_at = None
    evaluation.visible_to_student = True
    evaluation.save()


def _reject_company_evaluation(evaluation):
    evaluation.status = CompanyEvaluationStatus.REJECTED
    evaluation.advisor_rejected_at = timezone.now()
    evaluation.visible_to_student = False
    evaluation.save()


def _role_name(user):
    return getattr(user.role, "role_name", None) if getattr(user, "role", None) else None


class FinalIndustryEvaluationListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FinalIndustryEvaluationSerializer

    def get_queryset(self):
        user = self.request.user
        company_mentor_ids = CompanyMentor.objects.filter(user=user).values_list(
            "pk", flat=True
        )
        if company_mentor_ids:
            return FinalIndustryEvaluation.objects.filter(
                company_mentor__in=company_mentor_ids
            ).select_related(
                "internship__student__user",
                "internship__position__company",
                "company_mentor__user",
            )
        if _role_name(user) == "ADVISOR":
            internship_ids = advisor_internship_queryset(user).values_list(
                "pk", flat=True
            )
            return FinalIndustryEvaluation.objects.filter(
                internship_id__in=internship_ids
            ).select_related(
                "internship__student__user",
                "internship__position__company",
                "company_mentor__user",
            )
        return FinalIndustryEvaluation.objects.none()

    def perform_create(self, serializer):
        internship = serializer.validated_data.get("internship")
        company_mentor = CompanyMentor.objects.filter(
            user=self.request.user,
            id=internship.mentor_id,
        ).first()
        if company_mentor is None:
            raise serializers.ValidationError(
                "Only the company mentor assigned to this internship can submit."
            )
        if FinalIndustryEvaluation.objects.filter(internship=internship).exists():
            raise serializers.ValidationError(
                "Final evaluation for this internship already exists."
            )
        serializer.save(
            company_mentor=company_mentor,
            status=CompanyEvaluationStatus.SUBMITTED,
        )

        from core.services.audit_service import log_audit_event

        evaluation = serializer.instance
        log_audit_event(
            actor=self.request.user,
            action="EVALUATION_CREATED",
            target_type="FinalIndustryEvaluation",
            target_id=evaluation.id,
            description=f"Final industry evaluation created for internship {internship.id}.",
        )


class FinalIndustryEvaluationDetailAPIView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FinalIndustryEvaluationSerializer
    lookup_field = "id"

    def get_queryset(self):
        return FinalIndustryEvaluationListCreateAPIView(
            request=self.request
        ).get_queryset()


class AdvisorEvaluationListCreateAPIView(generics.ListCreateAPIView):
    """POST /api/evaluations/advisor/  GET /api/evaluations/advisor/"""

    permission_classes = [IsAuthenticated, IsAdvisorUser]
    serializer_class = AdvisorEvaluationSerializer

    def get_queryset(self):
        return (
            AdvisorEvaluation.objects.filter(advisor=self.request.user)
            .select_related(
                "internship__student__user",
                "internship__position__company",
                "advisor",
                "internship__overall_evaluation",
            )
            .prefetch_related("internship__weekly_logbooks", "internship__reports")
        )

    def perform_create(self, serializer):
        internship = serializer.validated_data["internship"]
        validate_advisor_assignment(self.request.user, internship)
        if AdvisorEvaluation.objects.filter(internship=internship).exists():
            raise serializers.ValidationError(
                "Advisor evaluation for this internship already exists."
            )
        serializer.save(
            advisor=self.request.user,
            status=AdvisorEvaluation.Status.PENDING,
        )


class AdvisorEvaluationDetailAPIView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated, IsAdvisorUser]
    serializer_class = AdvisorEvaluationSerializer
    lookup_field = "id"

    def get_queryset(self):
        return AdvisorEvaluationListCreateAPIView(
            request=self.request
        ).get_queryset()


class AdvisorEvaluationApproveAPIView(APIView):
    """PATCH /api/evaluations/advisor/<id>/approve/"""

    permission_classes = [IsAuthenticated, IsAdvisorUser]

    def patch(self, request, id):
        evaluation = get_object_or_404(
            AdvisorEvaluation.objects.select_related("internship"),
            pk=id,
            advisor=request.user,
        )
        if evaluation.status != AdvisorEvaluation.Status.PENDING:
            return Response(
                {"detail": "Only pending evaluations can be approved."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            validate_internship_prerequisites_for_advisor_eval(evaluation.internship)
        except DjangoValidationError as exc:
            return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)
        evaluation.status = AdvisorEvaluation.Status.APPROVED
        evaluation.approved_at = timezone.now()
        evaluation.save()
        serializer = AdvisorEvaluationSerializer(evaluation)
        return Response(
            {
                "message": "Advisor evaluation approved.",
                "evaluation": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class AdvisorEvaluationRejectAPIView(APIView):
    """PATCH /api/evaluations/advisor/<id>/reject/"""

    permission_classes = [IsAuthenticated, IsAdvisorUser]

    def patch(self, request, id):
        evaluation = get_object_or_404(
            AdvisorEvaluation,
            pk=id,
            advisor=request.user,
        )
        if evaluation.status != AdvisorEvaluation.Status.PENDING:
            return Response(
                {"detail": "Only pending evaluations can be rejected."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        body = AdvisorApprovalSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        evaluation.status = AdvisorEvaluation.Status.REJECTED
        evaluation.approved_at = None
        evaluation.save(update_fields=["status", "approved_at"])
        return Response(
            {"message": "Advisor evaluation rejected.", "evaluation_id": evaluation.id},
            status=status.HTTP_200_OK,
        )


class MonthlyIndustryEvaluationListCreateAPIView(generics.ListCreateAPIView):
    """Company mentor submits monthly evaluations."""

    permission_classes = [IsAuthenticated]
    serializer_class = MonthlyIndustryEvaluationSerializer

    def get_queryset(self):
        user = self.request.user
        mentor_ids = CompanyMentor.objects.filter(user=user).values_list("pk", flat=True)
        if mentor_ids:
            return MonthlyIndustryEvaluation.objects.filter(
                company_mentor__in=mentor_ids
            ).select_related("internship__student__user", "internship__position__company")
        if _role_name(user) == "ADVISOR":
            ids = advisor_internship_queryset(user).values_list("pk", flat=True)
            return MonthlyIndustryEvaluation.objects.filter(
                internship_id__in=ids
            ).select_related("internship__student__user", "internship__position__company")
        return MonthlyIndustryEvaluation.objects.none()

    def perform_create(self, serializer):
        internship = serializer.validated_data["internship"]
        company_mentor = CompanyMentor.objects.filter(
            user=self.request.user, id=internship.mentor_id
        ).first()
        if not company_mentor:
            raise serializers.ValidationError(
                "Only the assigned company mentor can submit monthly evaluations."
            )
        month = serializer.validated_data["month_number"]
        if MonthlyIndustryEvaluation.objects.filter(
            internship=internship, month_number=month
        ).exists():
            raise serializers.ValidationError(
                "Monthly evaluation for this month already exists."
            )
        serializer.save(
            company_mentor=company_mentor,
            status=CompanyEvaluationStatus.SUBMITTED,
        )


class FinalIndustryEvaluationApproveAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdvisorUser]

    def patch(self, request, id):
        evaluation = get_object_or_404(FinalIndustryEvaluation, pk=id)
        try:
            validate_advisor_assignment(request.user, evaluation.internship)
        except DjangoValidationError as exc:
            return Response(exc.message_dict, status=status.HTTP_403_FORBIDDEN)
        if evaluation.status != CompanyEvaluationStatus.SUBMITTED:
            return Response(
                {"detail": "Only submitted evaluations can be approved."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        _approve_company_evaluation(evaluation, request.user)
        return Response(
            FinalIndustryEvaluationSerializer(evaluation).data,
            status=status.HTTP_200_OK,
        )


class FinalIndustryEvaluationRejectAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdvisorUser]

    def patch(self, request, id):
        evaluation = get_object_or_404(FinalIndustryEvaluation, pk=id)
        try:
            validate_advisor_assignment(request.user, evaluation.internship)
        except DjangoValidationError as exc:
            return Response(exc.message_dict, status=status.HTTP_403_FORBIDDEN)
        _reject_company_evaluation(evaluation)
        return Response(
            {"message": "Final industry evaluation rejected.", "id": evaluation.id},
            status=status.HTTP_200_OK,
        )


class MonthlyIndustryEvaluationApproveAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdvisorUser]

    def patch(self, request, id):
        evaluation = get_object_or_404(MonthlyIndustryEvaluation, pk=id)
        try:
            validate_advisor_assignment(request.user, evaluation.internship)
        except DjangoValidationError as exc:
            return Response(exc.message_dict, status=status.HTTP_403_FORBIDDEN)
        if evaluation.status != CompanyEvaluationStatus.SUBMITTED:
            return Response(
                {"detail": "Only submitted evaluations can be approved."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        _approve_company_evaluation(evaluation, request.user)
        return Response(
            MonthlyIndustryEvaluationSerializer(evaluation).data,
            status=status.HTTP_200_OK,
        )


class MonthlyIndustryEvaluationRejectAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdvisorUser]

    def patch(self, request, id):
        evaluation = get_object_or_404(MonthlyIndustryEvaluation, pk=id)
        try:
            validate_advisor_assignment(request.user, evaluation.internship)
        except DjangoValidationError as exc:
            return Response(exc.message_dict, status=status.HTTP_403_FORBIDDEN)
        _reject_company_evaluation(evaluation)
        return Response(
            {"message": "Monthly evaluation rejected.", "id": evaluation.id},
            status=status.HTTP_200_OK,
        )


class AdvisorReportApproveAPIView(APIView):
    """Approve FINAL or MONTHLY report documents."""

    permission_classes = [IsAuthenticated, IsAdvisorUser]

    def patch(self, request, report_id):
        report = get_object_or_404(
            Report.objects.select_related("internship"),
            pk=report_id,
            report_type__in=("FINAL", "MONTHLY"),
        )
        try:
            validate_advisor_assignment(request.user, report.internship)
        except DjangoValidationError as exc:
            return Response(exc.message_dict, status=status.HTTP_403_FORBIDDEN)
        if report.report_type == "FINAL" and report.status not in (
            ReportReviewStatus.EXAMINER_APPROVED,
        ):
            return Response(
                {
                    "detail": "Final report must be approved by examiner before advisor approval."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if report.report_type == "MONTHLY" and report.status not in (
            ReportReviewStatus.SUBMITTED,
            "",
        ):
            return Response(
                {"detail": "Only submitted reports can be approved."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        report.status = ReportReviewStatus.ADVISOR_APPROVED
        report.reviewed_by = request.user
        report.reviewed_at = timezone.now()
        report.approved_at = timezone.now()
        report.save()
        return Response(
            {
                "message": "Report approved.",
                "report_id": report.id,
                "status": report.status,
                "approved_at": report.approved_at,
            },
            status=status.HTTP_200_OK,
        )


class AdvisorApprovalQueueAPIView(APIView):
    """GET /api/advisor/approval-queue/"""

    permission_classes = [IsAuthenticated, IsAdvisorUser]

    def get(self, request):
        internships = (
            advisor_internship_queryset(request.user)
            .select_related(
                "student__user",
                "position__company",
                "advisor_evaluation",
                "overall_evaluation",
                "final_industry_evaluation",
            )
            .prefetch_related(
                "weekly_logbooks",
                "reports",
                "examiner_evaluations",
                "monthly_industry_evaluations",
            )
        )
        items = [build_advisor_queue_item(i) for i in internships]
        serializer = AdvisorQueueSerializer(items, many=True)
        return Response(
            {
                "count": len(items),
                "queue": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class AdvisorApprovalQueueDetailAPIView(APIView):
    """GET /api/advisor/approval-queue/<internship_id>/ — documents, evals, examiner results."""

    permission_classes = [IsAuthenticated, IsAdvisorUser]

    def get(self, request, internship_id):
        from core.models import InternshipApplication

        internship = get_object_or_404(
            InternshipApplication.objects.select_related(
                "student__user", "position__company"
            ).prefetch_related(
                "weekly_logbooks",
                "reports",
                "examiner_evaluations",
                "monthly_industry_evaluations",
            ),
            pk=internship_id,
        )
        if not advisor_internship_queryset(request.user).filter(pk=internship.pk).exists():
            return Response(
                {"detail": "Not assigned to this internship."},
                status=status.HTTP_403_FORBIDDEN,
            )
        detail = build_advisor_queue_detail(internship)
        return Response(detail, status=status.HTTP_200_OK)


class OverallEvaluationDetailAPIView(generics.RetrieveAPIView):
    """Coordinator/advisor view of overall evaluation progress."""

    permission_classes = [IsAuthenticated]
    serializer_class = OverallInternshipEvaluationSerializer
    lookup_field = "internship_id"

    def get_queryset(self):
        user = self.request.user
        role = _role_name(user)
        qs = OverallInternshipEvaluation.objects.select_related(
            "internship__student__user",
            "advisor_evaluation",
            "company_evaluation",
            "examiner_one_evaluation",
            "examiner_two_evaluation",
        )
        if role == "COORDINATOR":
            staff = getattr(user, "staff", None)
            if staff:
                return qs.filter(
                    internship__student__department=staff.department
                )
        if role == "ADVISOR":
            ids = advisor_internship_queryset(user).values_list("pk", flat=True)
            return qs.filter(internship_id__in=ids)
        if role == "STUDENT":
            return qs.filter(
                internship__student__user=user,
                coordinator_approved=True,
                visible_to_student=True,
            )
        return qs.none()

    def get_object(self):
        from core.models import InternshipApplication

        internship_id = self.kwargs["internship_id"]
        internship = get_object_or_404(InternshipApplication, pk=internship_id)
        overall = get_or_create_overall(internship)
        queryset = self.get_queryset()
        if not queryset.filter(pk=overall.pk).exists():
            from rest_framework.exceptions import NotFound

            raise NotFound()
        return overall


class CoordinatorOverallApprovalAPIView(APIView):
    """PATCH /api/coordinator/overall-evaluation/<internship_id>/approve/"""

    permission_classes = [IsAuthenticated, IsCoordinatorUser]

    def patch(self, request, internship_id):
        from core.models import InternshipApplication

        internship = get_object_or_404(InternshipApplication, pk=internship_id)
        staff = getattr(request.user, "staff", None)
        if not staff or internship.student.department_id != staff.department_id:
            return Response(
                {"detail": "Not authorized for this department."},
                status=status.HTTP_403_FORBIDDEN,
            )

        overall = get_or_create_overall(internship)
        body = CoordinatorOverallApprovalSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        action = body.validated_data["action"]

        if action == "approve":
            ok, missing = can_coordinator_finalize(overall)
            if not ok:
                return Response(
                    {
                        "detail": "Cannot finalize until all evaluations are complete.",
                        "missing_requirements": missing,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            overall.coordinator_approved = True
            overall.coordinator_approved_at = timezone.now()
            overall.visible_to_student = True
            overall.status = OverallInternshipEvaluation.Status.APPROVED
            overall.approved_by = request.user
            overall.coordinator_comment = body.validated_data.get("comment", "")
            overall.calculate_final()
            overall.save()
            return Response(
                OverallInternshipEvaluationSerializer(overall).data,
                status=status.HTTP_200_OK,
            )

        overall.coordinator_approved = False
        overall.status = OverallInternshipEvaluation.Status.REJECTED
        overall.coordinator_comment = body.validated_data.get("comment", "")
        overall.save()
        return Response(
            {"message": "Overall evaluation rejected by coordinator."},
            status=status.HTTP_200_OK,
        )


class StudentInternshipResultsAPIView(APIView):
    """GET /api/students/internship-results/<internship_id>/ — visible after coordinator approval."""

    permission_classes = [IsAuthenticated]

    def get(self, request, internship_id):
        from core.models import InternshipApplication

        if not hasattr(request.user, "student_profile"):
            return Response(
                {"detail": "Only students can access internship results."},
                status=status.HTTP_403_FORBIDDEN,
            )

        internship = get_object_or_404(
            InternshipApplication,
            pk=internship_id,
            student=request.user.student_profile,
        )
        overall = getattr(internship, "overall_evaluation", None)
        if (
            not overall
            or not overall.coordinator_approved
            or not overall.visible_to_student
        ):
            return Response(
                {
                    "detail": "Results are not yet available. Await coordinator approval.",
                    "coordinator_approved": False,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        status_payload = build_student_evaluation_status(internship)
        data = {
            "coordinator_approved": True,
            "coordinator_approved_at": overall.coordinator_approved_at,
            "final_grade": overall.final_grade,
            "final_total_score": overall.final_total_score,
            "advisor_evaluation": None,
            "examiner_evaluations": [],
            "company_evaluation": None,
            "monthly_evaluations": status_payload["monthly_evaluations"],
            "final_evaluation": status_payload["final_evaluation"],
            "documents": status_payload["documents"],
            "examiner_progress": status_payload["examiner_progress"],
        }
        if overall.advisor_evaluation_id:
            data["advisor_evaluation"] = AdvisorEvaluationSerializer(
                overall.advisor_evaluation
            ).data
        if overall.company_evaluation_id:
            data["company_evaluation"] = FinalIndustryEvaluationSerializer(
                overall.company_evaluation
            ).data
        for ev in [overall.examiner_one_evaluation, overall.examiner_two_evaluation]:
            if ev:
                data["examiner_evaluations"].append(
                    ExaminerEvaluationSerializer(ev).data
                )
        return Response(data, status=status.HTTP_200_OK)


class StudentEvaluationStatusAPIView(APIView):
    """
    GET /api/students/evaluation-status/<internship_id>/
    Students see company submission/advisor approval status and timestamps.
    Numeric scores appear only after coordinator final approval.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, internship_id):
        from core.models import InternshipApplication

        if not hasattr(request.user, "student_profile"):
            return Response(
                {"detail": "Only students can access evaluation status."},
                status=status.HTTP_403_FORBIDDEN,
            )
        internship = get_object_or_404(
            InternshipApplication,
            pk=internship_id,
            student=request.user.student_profile,
        )
        return Response(
            build_student_evaluation_status(internship),
            status=status.HTTP_200_OK,
        )
