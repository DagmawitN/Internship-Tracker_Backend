from django.db import models
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
    ExaminerEvaluation,
    FinalIndustryEvaluation,
    InternshipApplication,
    MonthlyIndustryEvaluation,
    OverallInternshipEvaluation,
    Report,
    ReportReviewStatus,
)
from core.permissions import IsAdvisorUser, IsCoordinatorUser, IsExaminerUser
from core.serializers.evaluation_serializers import (
    AdvisorApprovalSerializer,
    AdvisorEvaluationSerializer,
    AdvisorQueueSerializer,
    CoordinatorOverallApprovalSerializer,
    ExaminerEvaluationSerializer,
    ExaminerOverallApprovalSerializer,
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
    examiner_internship_queryset,
    get_or_create_overall,
    sync_overall_from_advisor,
    sync_overall_from_company,
    sync_overall_from_examiner,
    sync_overall_from_examiner_signoff,
)
from core.evaluation_validators import (
    validate_advisor_assignment,
    validate_internship_prerequisites_for_advisor_eval,
    validate_examiner_assignment,
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
            # advisor_internship_queryset returns InternshipApplication PKs,
            # but FinalIndustryEvaluation.internship → Internship (execution record).
            # Resolve via student: get students from advisor's applications, then
            # find Internship execution records for those students.
            from core.models import Internship as InternshipRecord
            app_qs = advisor_internship_queryset(user)
            student_ids = app_qs.values_list("student_id", flat=True)
            execution_ids = InternshipRecord.objects.filter(
                student_id__in=student_ids
            ).values_list("pk", flat=True)
            return FinalIndustryEvaluation.objects.filter(
                internship_id__in=execution_ids
            ).select_related(
                "internship__student__user",
                "internship__position__company",
                "company_mentor__user",
            )
        if _role_name(user) == "COORDINATOR":
            staff = getattr(user, "staff", None)
            qs = FinalIndustryEvaluation.objects.select_related(
                "internship__student__user",
                "internship__position__company",
                "company_mentor__user",
            )
            if staff and staff.department_id:
                qs = qs.filter(internship__student__department=staff.department)
            internship_id = self.request.query_params.get("internship_id")
            if internship_id:
                from core.models import Internship as InternshipRecord

                internship_pks = set()
                if InternshipRecord.objects.filter(pk=internship_id).exists():
                    internship_pks.add(int(internship_id))
                app_internships = InternshipRecord.objects.filter(
                    student__applications__id=internship_id
                ).values_list("pk", flat=True)
                internship_pks.update(app_internships)
                if internship_pks:
                    qs = qs.filter(internship_id__in=internship_pks)
                else:
                    qs = qs.none()
            return qs
        if _role_name(user) == "STUDENT":
            student = getattr(user, "student_profile", None)
            if not student:
                return FinalIndustryEvaluation.objects.none()
            return FinalIndustryEvaluation.objects.filter(
                internship__student=student
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


class CoordinatorAdvisorEvaluationAPIView(APIView):
    """
    GET /api/evaluations/advisor/for-coordinator/?internship_id=<id>
    Allows coordinators (and advisors) to fetch the advisor evaluation for a
    given InternshipApplication PK.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        role = _role_name(user)
        if role not in ("COORDINATOR", "ADVISOR", "STUDENT"):
            return Response(
                {"detail": "Only coordinators, advisors, and the owning student can access this endpoint."},
                status=status.HTTP_403_FORBIDDEN,
            )

        internship_id = request.query_params.get("internship_id")
        if not internship_id:
            return Response(
                {"error": "internship_id query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        internship = get_object_or_404(InternshipApplication, pk=internship_id)

        # Coordinators may only view evals for students in their department.
        if role == "COORDINATOR":
            staff = getattr(user, "staff", None)
            if staff and hasattr(internship.student, "department"):
                if internship.student.department != staff.department:
                    return Response(
                        {"detail": "Not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

        # Student may only view their own internship application's advisor evaluation.
        if role == "STUDENT":
            student_profile = getattr(user, "student_profile", None)
            if not student_profile or internship.student_id != student_profile.id:
                return Response(
                    {"detail": "Not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        evaluation = AdvisorEvaluation.objects.filter(internship=internship).first()
        if not evaluation:
            return Response(None, status=status.HTTP_200_OK)

        serializer = AdvisorEvaluationSerializer(evaluation)
        return Response(serializer.data)


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
        if _role_name(user) == "COORDINATOR":
            staff = getattr(user, "staff", None)
            qs = MonthlyIndustryEvaluation.objects.select_related(
                "internship__student__user",
                "internship__position__company",
            )
            if staff and staff.department_id:
                qs = qs.filter(internship__student__department=staff.department)
            internship_id = self.request.query_params.get("internship_id")
            if internship_id:
                qs = qs.filter(internship_id=internship_id)
            return qs
        if _role_name(user) == "STUDENT":
            student = getattr(user, "student_profile", None)
            if not student:
                return MonthlyIndustryEvaluation.objects.none()
            qs = MonthlyIndustryEvaluation.objects.filter(
                internship__student=student
            ).select_related("internship__student__user", "internship__position__company")
            internship_id = self.request.query_params.get("internship_id")
            if internship_id:
                qs = qs.filter(internship_id=internship_id)
            return qs
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
        # FinalIndustryEvaluation.internship points to an Internship execution record.
        # The advisor assignment validations expect an InternshipApplication instance.
        from core.models import InternshipApplication, Internship as InternshipRecord

        internship_obj = evaluation.internship
        application = None
        if isinstance(internship_obj, InternshipApplication):
            application = internship_obj
        else:
            application = (
                InternshipApplication.objects.filter(
                    student=internship_obj.student, position=internship_obj.position
                ).first()
            )
        if application is None:
            return Response({"detail": "Associated internship application not found."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            validate_advisor_assignment(request.user, application)
        except DjangoValidationError as exc:
            return Response(exc.message_dict, status=status.HTTP_403_FORBIDDEN)
        if evaluation.status != CompanyEvaluationStatus.SUBMITTED:
            return Response(
                {"detail": "Only submitted evaluations can be approved."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        _approve_company_evaluation(evaluation, request.user)
        # Also mark the related InternshipApplication advisor review as completed
        from core.models import Advisor as AdvisorModel

        try:
            advisor_obj = AdvisorModel.objects.filter(user=request.user).first()
            if application:
                # assign advisor if not set
                if advisor_obj and getattr(application, "advisor_id", None) != advisor_obj.pk:
                    application.advisor = advisor_obj
                if application.advisor_status == "PENDING":
                    application.advisor_status = "APPROVED"
                    application.save(update_fields=["advisor", "advisor_status"])
        except Exception:
            # best-effort: don't block approval if updating application fails
            pass
        return Response(
            FinalIndustryEvaluationSerializer(evaluation).data,
            status=status.HTTP_200_OK,
        )


class FinalIndustryEvaluationRejectAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdvisorUser]

    def patch(self, request, id):
        evaluation = get_object_or_404(FinalIndustryEvaluation, pk=id)
        from core.models import InternshipApplication

        internship_obj = evaluation.internship
        application = None
        if isinstance(internship_obj, InternshipApplication):
            application = internship_obj
        else:
            application = (
                InternshipApplication.objects.filter(
                    student=internship_obj.student, position=internship_obj.position
                ).first()
            )
        if application is None:
            return Response({"detail": "Associated internship application not found."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            validate_advisor_assignment(request.user, application)
        except DjangoValidationError as exc:
            return Response(exc.message_dict, status=status.HTTP_403_FORBIDDEN)
        _reject_company_evaluation(evaluation)
        # Also mark the related InternshipApplication advisor review as rejected
        from core.models import Advisor as AdvisorModel

        try:
            advisor_obj = AdvisorModel.objects.filter(user=request.user).first()
            if application:
                if advisor_obj and getattr(application, "advisor_id", None) != advisor_obj.pk:
                    application.advisor = advisor_obj
                if application.advisor_status == "PENDING":
                    application.advisor_status = "REJECTED"
                    application.save(update_fields=["advisor", "advisor_status"])
        except Exception:
            pass
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

            # Mark the related Internship execution record as COMPLETED
            from core.models import Internship as InternshipRecord
            internship_record = InternshipRecord.objects.filter(
                student=internship.student,
                position=internship.position
            ).order_by("-id").first()
            if internship_record:
                internship_record.status = "COMPLETED"
                internship_record.save(update_fields=["status"])

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


# ---------------------------------------------------------------------------
# Examiner: list own evaluations + submit/update
# ---------------------------------------------------------------------------

class ExaminerEvaluationListCreateAPIView(APIView):
    """
    GET  /api/evaluations/examiner/          — list evaluations submitted by this examiner
    POST /api/evaluations/examiner/          — submit or update an evaluation
    """

    permission_classes = [IsAuthenticated, IsExaminerUser]

    def get(self, request):
        qs = (
            ExaminerEvaluation.objects.filter(examiner=request.user)
            .select_related(
                "internship__student__user",
                "internship__position__company",
            )
            .order_by("-submitted_at")
        )
        serializer = ExaminerEvaluationSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        from core.models import AdvisorAssignment

        internship_id = request.data.get("internship")
        if not internship_id:
            return Response(
                {"error": "internship field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        internship = get_object_or_404(InternshipApplication, pk=internship_id)

        # Verify this examiner is assigned to this student
        is_assigned = AdvisorAssignment.objects.filter(
            advisor=request.user,
            internship=internship,
            role="EXAMINER",
        ).exists()
        if not is_assigned:
            return Response(
                {"error": "You are not assigned as examiner for this student."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Upsert — one evaluation per (internship, examiner)
        existing = ExaminerEvaluation.objects.filter(
            internship=internship, examiner=request.user
        ).first()

        serializer = ExaminerEvaluationSerializer(
            existing, data=request.data, partial=bool(existing)
        )
        serializer.is_valid(raise_exception=True)

        # Store the full granular form_data from the frontend
        form_data = request.data.get("form_data", {})

        if existing:
            instance = serializer.save(form_data=form_data)
            created = False
        else:
            instance = serializer.save(examiner=request.user, form_data=form_data)
            created = True

        from core.services.audit_service import log_audit_event
        log_audit_event(
            actor=request.user,
            action="EXAMINER_EVALUATION_SUBMITTED",
            target_type="ExaminerEvaluation",
            target_id=instance.id,
            description=(
                f"Examiner {request.user.email} {'submitted' if created else 'updated'} "
                f"evaluation for {internship.student.user.email}."
            ),
        )

        return Response(
            ExaminerEvaluationSerializer(instance).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class ExaminerEvaluationDetailAPIView(APIView):
    """
    GET   /api/evaluations/examiner/<id>/   — retrieve one evaluation
    PATCH /api/evaluations/examiner/<id>/   — update scores
    """

    permission_classes = [IsAuthenticated, IsExaminerUser]

    def _get_object(self, pk, user):
        obj = get_object_or_404(ExaminerEvaluation, pk=pk)
        if obj.examiner != user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You can only access your own evaluations.")
        return obj

    def get(self, request, pk):
        obj = self._get_object(pk, request.user)
        return Response(ExaminerEvaluationSerializer(obj).data)

    def patch(self, request, pk):
        obj = self._get_object(pk, request.user)
        form_data = request.data.get("form_data", obj.form_data)
        serializer = ExaminerEvaluationSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save(form_data=form_data)
        return Response(ExaminerEvaluationSerializer(instance).data)


class ExaminerOverallApprovalAPIView(APIView):
    """PATCH /api/evaluations/examiner/<internship_id>/overall-approval/"""

    permission_classes = [IsAuthenticated, IsExaminerUser]

    def patch(self, request, internship_id):
        internship = get_object_or_404(InternshipApplication, pk=internship_id)

        try:
            validate_examiner_assignment(request.user, internship)
        except DjangoValidationError as exc:
            payload = exc.message_dict if hasattr(exc, "message_dict") else {"detail": exc.messages[0]}
            return Response(payload, status=status.HTTP_403_FORBIDDEN)

        overall = get_or_create_overall(internship)
        if not overall.advisor_approved:
            return Response(
                {"detail": "Advisor approval is required before examiner sign-off."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from core.models import AdvisorAssignment

        serializer = ExaminerOverallApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        requested_slot = serializer.validated_data.get("slot")

        # Determine the user's correct slot based on AdvisorAssignment order (by ID)
        assignments = (
            AdvisorAssignment.objects.filter(internship=internship, role="EXAMINER")
            .order_by("id")
            .values_list("advisor_id", flat=True)
        )
        assignments_list = list(assignments)

        try:
            # Slot is 1-indexed
            actual_slot_index = assignments_list.index(request.user.id)
            actual_slot = str(actual_slot_index + 1)
        except ValueError:
            return Response(
                {"detail": "User is not assigned as an examiner for this internship."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if requested_slot and str(requested_slot) != actual_slot:
            return Response(
                {"detail": f"Incorrect slot provided. You are assigned to slot {actual_slot}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        slot = actual_slot
        approvals = dict(overall.examiner_approval_state or {})
        approvals[slot] = {
            "approved": True,
            "approved_at": timezone.now().isoformat(),
            "examiner_id": request.user.id,
        }
        overall.examiner_approval_state = approvals
        overall.save(update_fields=["examiner_approval_state", "updated_at"])

        # Check if all examiners have now signed off
        sync_overall_from_examiner_signoff(internship.id)
        overall.refresh_from_db()

        return Response(
            {
                "message": f"Examiner {slot} overall sign-off recorded.",
                "overall": OverallInternshipEvaluationSerializer(overall).data,
            },
            status=status.HTTP_200_OK,
        )


class ExaminerOverallQueueAPIView(APIView):
    """GET /api/evaluations/examiner/overall-queue/"""

    permission_classes = [IsAuthenticated, IsExaminerUser]

    def get(self, request):
        assigned = examiner_internship_queryset(request.user).select_related(
            "student__user",
            "position__company",
            "advisor",
            "overall_evaluation",
        )
        user_id = str(request.user.id)
        queue = []

        for internship in assigned:
            overall = get_or_create_overall(internship)
            if not overall.advisor_approved:
                continue

            approvals = dict(overall.examiner_approval_state or {})
            if any(str(item.get("examiner_id")) == user_id and item.get("approved") for item in approvals.values()):
                continue

            queue.append(OverallInternshipEvaluationSerializer(overall).data)

        return Response({"count": len(queue), "queue": queue}, status=status.HTTP_200_OK)


class CoordinatorOverallQueueAPIView(APIView):
    """GET /api/evaluations/coordinator/overall-queue/"""

    permission_classes = [IsAuthenticated, IsCoordinatorUser]

    def get(self, request):
        staff = getattr(request.user, "staff", None)
        if not staff or not staff.department_id:
            return Response(
                {"detail": "Coordinator must be assigned to a department."},
                status=status.HTTP_403_FORBIDDEN,
            )

        assigned = InternshipApplication.objects.filter(
            student__department=staff.department
        ).select_related(
            "student__user",
            "position__company",
            "advisor",
            "overall_evaluation",
        )
        from core.models import OverallInternshipEvaluation as _OIE
        queue = []

        for internship in assigned:
            overall = get_or_create_overall(internship)
            
            # Re-fetch with relations for score calculation
            try:
                overall = _OIE.objects.select_related(
                    "advisor_evaluation",
                    "examiner_one_evaluation",
                    "examiner_two_evaluation",
                    "company_evaluation",
                    "internship__student__user",
                ).get(pk=overall.pk)
            except _OIE.DoesNotExist:
                continue

            data = OverallInternshipEvaluationSerializer(overall).data
            
            # Determine if it needs coordinator approval (the "queue" criteria)
            approvals = dict(overall.examiner_approval_state or {})
            has_examiner_approvals = approvals and all(item.get("approved") for item in approvals.values())
            
            data["is_pending_approval"] = (
                overall.advisor_approved and 
                has_examiner_approvals and 
                not overall.coordinator_approved
            )
            
            queue.append(data)

        return Response({"count": len(queue), "queue": queue}, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Company: upsert monthly evaluation (create or update)
# ---------------------------------------------------------------------------

class CompanyMonthlyEvaluationUpsertAPIView(APIView):
    """
    GET  /api/evaluations/company/monthly/?internship_id=<id>
         List all monthly evaluations for the company's interns (or filter by internship).

    POST /api/evaluations/company/monthly/
         Create or update a monthly evaluation.
         Body: { internship, month_number, work_quality_score, punctuality_score,
                 attitude_score, initiative_score, comments, form_data }
    """

    permission_classes = [IsAuthenticated]

    def _get_mentor(self, user):
        mentor = CompanyMentor.objects.filter(user=user).first()
        if not mentor:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only company mentors can access this endpoint.")
        return mentor

    def get(self, request):
        mentor = self._get_mentor(request.user)
        qs = MonthlyIndustryEvaluation.objects.filter(
            company_mentor=mentor
        ).select_related(
            "internship__student__user",
            "internship__position__company",
        ).order_by("internship_id", "month_number")

        internship_id = request.query_params.get("internship_id")
        if internship_id:
            qs = qs.filter(internship_id=internship_id)

        serializer = MonthlyIndustryEvaluationSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        mentor = self._get_mentor(request.user)

        internship_id = request.data.get("internship")
        month_number = request.data.get("month_number")

        if not internship_id or not month_number:
            return Response(
                {"error": "internship and month_number are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        internship = get_object_or_404(InternshipApplication, pk=internship_id)

        # Upsert — allow re-submission after rejection
        existing = MonthlyIndustryEvaluation.objects.filter(
            internship=internship, month_number=month_number
        ).first()

        form_data = request.data.get("form_data", {})

        if existing:
            # Update existing record
            serializer = MonthlyIndustryEvaluationSerializer(
                existing, data=request.data, partial=True
            )
            serializer.is_valid(raise_exception=True)
            instance = serializer.save(
                status=CompanyEvaluationStatus.SUBMITTED,
                form_data=form_data,
            )
            created = False
        else:
            serializer = MonthlyIndustryEvaluationSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            instance = serializer.save(
                company_mentor=mentor,
                status=CompanyEvaluationStatus.SUBMITTED,
                form_data=form_data,
            )
            created = True

        from core.services.audit_service import log_audit_event
        log_audit_event(
            actor=request.user,
            action="MONTHLY_EVAL_SUBMITTED",
            target_type="MonthlyIndustryEvaluation",
            target_id=instance.id,
            description=(
                f"Company mentor {request.user.email} {'submitted' if created else 'updated'} "
                f"Month {month_number} evaluation for internship {internship_id}."
            ),
        )
        from core.services.evaluation_workflow import sync_overall_from_company
        sync_overall_from_company(instance)

        return Response(
            MonthlyIndustryEvaluationSerializer(instance).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Company: upsert final evaluation (create or update)
# ---------------------------------------------------------------------------

class CompanyFinalEvaluationUpsertAPIView(APIView):
    """
    GET  /api/evaluations/company/final/?internship_id=<id>
         List final evaluations for the company's interns.

    POST /api/evaluations/company/final/
         Create or update a final evaluation.
         Body: all FinalIndustryEvaluation score fields + form_data
    """

    permission_classes = [IsAuthenticated]

    def _get_mentor(self, user):
        mentor = CompanyMentor.objects.filter(user=user).first()
        if not mentor:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only company mentors can access this endpoint.")
        return mentor

    def get(self, request):
        mentor = self._get_mentor(request.user)
        qs = FinalIndustryEvaluation.objects.filter(
            company_mentor=mentor
        ).select_related(
            "internship__student__user",
            "internship__position__company",
        )

        internship_id = request.query_params.get("internship_id")
        if internship_id:
            from core.models import Internship as InternshipRecord
            # internship_id may be an InternshipApplication PK or an Internship PK
            # Try both: first as Internship PK, then resolve via InternshipApplication
            internship_pks = set()
            # Direct Internship PK
            if InternshipRecord.objects.filter(pk=internship_id).exists():
                internship_pks.add(int(internship_id))
            # Via InternshipApplication → find matching Internship records
            app_internships = InternshipRecord.objects.filter(
                student__applications__id=internship_id
            ).values_list("pk", flat=True)
            internship_pks.update(app_internships)

            if internship_pks:
                qs = qs.filter(internship_id__in=internship_pks)
            else:
                qs = qs.none()

        serializer = FinalIndustryEvaluationSerializer(qs.distinct(), many=True)
        return Response(serializer.data)

    def post(self, request):
        mentor = self._get_mentor(request.user)

        internship_id = (
            request.data.get("internship")
            or request.data.get("internship_id")
            or request.data.get("application_id")
        )
        if not internship_id:
            return Response(
                {"error": "internship field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from core.models import Internship as InternshipRecord
        # Try direct Internship PK first
        internship_record = InternshipRecord.objects.filter(pk=internship_id).first()

        # If not found, resolve via InternshipApplication PK
        if not internship_record:
            internship_record = InternshipRecord.objects.filter(
                student__applications__id=internship_id
            ).order_by("-id").first()

        # If still not found, try to find via student who has this application
        if not internship_record:
            try:
                app = InternshipApplication.objects.get(pk=internship_id)
                internship_record = InternshipRecord.objects.filter(
                    student=app.student
                ).order_by("-id").first()

                # Legacy fallback: older records may not have had an execution row created.
                # Accept any application that is coordinator-approved or student-accepted.
                app_is_active = (
                    app.student_decision == "ACCEPTED"
                    or app.dept_status == "APPROVED"
                    or app.mentor_status == "ACCEPTED"
                )
                if not internship_record and app_is_active:
                    internship_record = InternshipRecord.objects.create(
                        student=app.student,
                        position=app.position,
                        company=app.position.company,
                        supervisor=app.supervisor,
                        mentor=app.mentor,
                        start_date=app.requested_start_date,
                        end_date=app.requested_end_date,
                        status="NOT_STARTED",
                    )
            except InternshipApplication.DoesNotExist:
                pass

        if not internship_record:
            return Response(
                {"error": "No internship execution record found for this application. The internship may not have started yet."},
                status=status.HTTP_404_NOT_FOUND,
            )

        form_data = request.data.get("form_data", {})
        data = {**request.data, "internship": internship_record.pk}

        existing = FinalIndustryEvaluation.objects.filter(
            internship=internship_record
        ).first()

        if existing:
            serializer = FinalIndustryEvaluationSerializer(
                existing, data=data, partial=True,
                context={"request": request}
            )
            serializer.is_valid(raise_exception=True)
            instance = serializer.save(
                status=CompanyEvaluationStatus.SUBMITTED,
                form_data=form_data,
            )
            created = False
        else:
            serializer = FinalIndustryEvaluationSerializer(
                data=data, context={"request": request}
            )
            serializer.is_valid(raise_exception=True)
            instance = serializer.save(
                company_mentor=mentor,
                status=CompanyEvaluationStatus.SUBMITTED,
                form_data=form_data,
            )
            created = True

        from core.services.audit_service import log_audit_event
        log_audit_event(
            actor=request.user,
            action="FINAL_EVAL_SUBMITTED",
            target_type="FinalIndustryEvaluation",
            target_id=instance.id,
            description=(
                f"Company mentor {request.user.email} {'submitted' if created else 'updated'} "
                f"final evaluation for internship {internship_record.id}."
            ),
        )
        from core.services.evaluation_workflow import sync_overall_from_company
        sync_overall_from_company(instance)

        return Response(
            FinalIndustryEvaluationSerializer(instance).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Advisor: view examiner evaluations for assigned students
# ---------------------------------------------------------------------------

class AdvisorExaminerEvaluationsAPIView(APIView):
    """
    GET /api/evaluations/examiner/for-advisor/
    Returns ExaminerEvaluation records for students assigned to the
    authenticated advisor OR for a coordinator's department.
    Optional: ?internship_id=<id> to filter to one student.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from core.models import Advisor, AdvisorAssignment

        role = _role_name(request.user)
        internship_id = request.query_params.get("internship_id")

        # Coordinator: return evals for their department or a specific internship
        if role == "COORDINATOR":
            if internship_id:
                qs = ExaminerEvaluation.objects.filter(
                    internship_id=internship_id
                )
            else:
                staff = getattr(request.user, "staff", None)
                if not staff:
                    return Response([])
                qs = ExaminerEvaluation.objects.filter(
                    internship__student__department=staff.department
                )
            qs = qs.select_related(
                "internship__student__user",
                "internship__position__company",
                "examiner",
            ).order_by("internship_id", "-submitted_at")
            serializer = ExaminerEvaluationSerializer(qs, many=True)
            return Response(serializer.data)

        # Advisor: return evals for their assigned students
        if role != "ADVISOR":
            return Response(
                {"detail": "Only advisors and coordinators can access this endpoint."},
                status=status.HTTP_403_FORBIDDEN,
            )

        advisor_profile = Advisor.objects.filter(user=request.user).first()
        student_ids = []
        if advisor_profile:
            student_ids = list(
                advisor_profile.assigned_students.values_list("id", flat=True)
            )

        assignment_internship_ids = AdvisorAssignment.objects.filter(
            advisor=request.user, role="ADVISOR"
        ).values_list("internship_id", flat=True)

        # Also catch applications where the student's advisor field points to this advisor
        if advisor_profile:
            advisor_student_ids = list(
                InternshipApplication.objects.filter(
                    student__advisor=advisor_profile
                ).values_list("student_id", flat=True)
            )
            student_ids = list(set(student_ids) | set(advisor_student_ids))

        qs = ExaminerEvaluation.objects.filter(
            models.Q(internship__student_id__in=student_ids) |
            models.Q(internship_id__in=assignment_internship_ids)
        ).select_related(
            "internship__student__user",
            "internship__position__company",
            "examiner",
        ).order_by("internship_id", "-submitted_at")

        if internship_id:
            qs = qs.filter(internship_id=internship_id)

        serializer = ExaminerEvaluationSerializer(qs, many=True)
        return Response(serializer.data)


class StudentExaminerEvaluationsAPIView(APIView):
    """
    GET /api/evaluations/examiner/for-student/?internship_id=<id>
    Returns ExaminerEvaluation records for a specific internship if the
    authenticated user is the student on that internship.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        internship_id = request.query_params.get("internship_id")
        if not internship_id:
            return Response([], status=status.HTTP_200_OK)

        from core.models import InternshipApplication

        # Ensure the requesting user is the student for this internship
        internship = get_object_or_404(
            InternshipApplication,
            pk=internship_id,
            student=getattr(request.user, "student_profile", None),
        )

        qs = (
            ExaminerEvaluation.objects.filter(internship_id=internship_id)
            .select_related(
                "internship__student__user",
                "internship__position__company",
                "examiner",
            )
            .order_by("-submitted_at")
        )
        serializer = ExaminerEvaluationSerializer(qs, many=True)
        return Response(serializer.data)
