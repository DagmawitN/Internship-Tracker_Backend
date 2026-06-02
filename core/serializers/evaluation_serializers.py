from rest_framework import serializers

from core.evaluation_constants import ADVISOR_SCORE_FIELDS
from core.evaluation_validators import (
    validate_advisor_assignment,
    validate_advisor_score_fields,
    validate_internship_prerequisites_for_advisor_eval,
)
from core.models import (
    AdvisorEvaluation,
    CompanyMentor,
    ExaminerEvaluation,
    FinalIndustryEvaluation,
    Internship,
    InternshipApplication,
    MonthlyIndustryEvaluation,
    OverallInternshipEvaluation,
)


class ScoreValidationMixin:
    """Mixin for per-field score validation against configured maxima."""

    score_field_limits = {}

    def _validate_bounded_score(self, value, field_name):
        max_score = self.score_field_limits.get(field_name)
        if max_score is None:
            return value
        if value < 0:
            raise serializers.ValidationError(f"{field_name} cannot be negative.")
        if value > max_score:
            raise serializers.ValidationError(
                f"{field_name} cannot exceed {max_score}."
            )
        return value


class FinalIndustryEvaluationSerializer(serializers.ModelSerializer):
    student_full_name = serializers.SerializerMethodField()
    student_id = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    evaluator_name = serializers.SerializerMethodField()

    class Meta:
        model = FinalIndustryEvaluation
        fields = [
            "id",
            "internship",
            "student_full_name",
            "student_id",
            "company_name",
            "evaluator_name",
            "submitted_at",
            "status",
            "advisor_reviewer",
            "advisor_approved_at",
            "advisor_rejected_at",
            "visible_to_student",
            "knowledge_about_task",
            "problem_solving",
            "quality_of_work",
            "punctuality_in_production",
            "initiative",
            "section_a_total",
            "dedication",
            "cooperation",
            "discipline",
            "responsibility",
            "socialization",
            "communication",
            "decision_making",
            "section_b_total",
            "student_potential",
            "overall_comments",
            "would_offer_job",
            "total_mark",
            "overall_student_performance",
            "form_data",
        ]
        read_only_fields = [
            "id",
            "submitted_at",
            "status",
            "advisor_reviewer",
            "advisor_approved_at",
            "advisor_rejected_at",
            "visible_to_student",
            "section_a_total",
            "section_b_total",
            "total_mark",
            "overall_student_performance",
        ]

    def validate_score(self, value, field_name):
        if not (0 <= value <= 5):
            raise serializers.ValidationError(
                f"{field_name} must be between 0 and 5."
            )
        return value

    def validate_knowledge_about_task(self, value):
        return self.validate_score(value, "knowledge_about_task")

    def validate_problem_solving(self, value):
        return self.validate_score(value, "problem_solving")

    def validate_quality_of_work(self, value):
        return self.validate_score(value, "quality_of_work")

    def validate_punctuality_in_production(self, value):
        return self.validate_score(value, "punctuality_in_production")

    def validate_initiative(self, value):
        return self.validate_score(value, "initiative")

    def validate_dedication(self, value):
        return self.validate_score(value, "dedication")

    def validate_cooperation(self, value):
        return self.validate_score(value, "cooperation")

    def validate_discipline(self, value):
        return self.validate_score(value, "discipline")

    def validate_responsibility(self, value):
        return self.validate_score(value, "responsibility")

    def validate_socialization(self, value):
        return self.validate_score(value, "socialization")

    def validate_communication(self, value):
        return self.validate_score(value, "communication")

    def validate_decision_making(self, value):
        return self.validate_score(value, "decision_making")

    def validate_internship(self, value):
        # Allow both ONGOING and COMPLETED internships — company submits during active placement
        return value

    def validate(self, data):
        internship = data.get("internship") or (
            self.instance.internship if self.instance else None
        )
        if internship is None:
            return data

        qs = FinalIndustryEvaluation.objects.filter(internship=internship)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "Final evaluation for this internship already exists."
            )

        request = self.context.get("request")
        if request and request.user.is_authenticated:
            company_mentor = CompanyMentor.objects.filter(
                user=request.user,
                id=internship.mentor_id,
            ).first()
            if company_mentor is None:
                raise serializers.ValidationError(
                    "Only the company mentor assigned to this internship can submit."
                )
        return data

    def get_student_full_name(self, obj):
        user = obj.internship.student.user
        return f"{user.first_name} {user.last_name}".strip() or user.username

    def get_student_id(self, obj):
        return obj.internship.student.student_id

    def get_company_name(self, obj):
        return obj.internship.position.company.company_name

    def get_evaluator_name(self, obj):
        if obj.company_mentor:
            u = obj.company_mentor.user
            return u.get_full_name() or u.username
        return "Unknown"


class AdvisorEvaluationSerializer(ScoreValidationMixin, serializers.ModelSerializer):
    score_field_limits = ADVISOR_SCORE_FIELDS
    student_full_name = serializers.SerializerMethodField()
    student_id = serializers.SerializerMethodField()
    advisor_name = serializers.SerializerMethodField()
    internship_id = serializers.IntegerField(source="internship.id", read_only=True)
    company_name = serializers.SerializerMethodField()
    workflow_status = serializers.SerializerMethodField()

    class Meta:
        model = AdvisorEvaluation
        fields = [
            "id",
            "internship",
            "internship_id",
            "student_full_name",
            "student_id",
            "company_name",
            "advisor",
            "advisor_name",
            "submitted_at",
            "approved_at",
            "status",
            "report_format_score",
            "organization_background_score",
            "activities_score",
            "data_figure_table_score",
            "report_content_score",
            "recommendation_score",
            "conclusion_score",
            "report_total",
            "weighted_report_mark",
            "pictures_and_data_score",
            "weekly_summary_score",
            "daily_detail_score",
            "improvement_score",
            "initiative_score",
            "logbook_total",
            "weighted_logbook_mark",
            "understanding_objective_score",
            "engagement_score",
            "discipline_score",
            "student_performance_total",
            "weighted_student_performance_mark",
            "total_marks",
            "final_weighted_mark",
            "workflow_status",
        ]
        read_only_fields = [
            "id",
            "advisor",
            "submitted_at",
            "approved_at",
            "status",
            "report_total",
            "weighted_report_mark",
            "logbook_total",
            "weighted_logbook_mark",
            "student_performance_total",
            "weighted_student_performance_mark",
            "total_marks",
            "final_weighted_mark",
            "workflow_status",
        ]

    def validate_internship(self, value):
        if value is None:
            raise serializers.ValidationError("Internship is required.")
        return value

    def validate(self, data):
        internship = data.get("internship") or (
            self.instance.internship if self.instance else None
        )
        if internship is None:
            return data

        qs = AdvisorEvaluation.objects.filter(internship=internship)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "Advisor evaluation for this internship already exists."
            )

        request = self.context.get("request")
        if request and request.user.is_authenticated and self.instance is None:
            validate_advisor_assignment(request.user, internship)

        # Validate all score fields on create/update
        merged = {}
        if self.instance:
            for field in ADVISOR_SCORE_FIELDS:
                merged[field] = getattr(self.instance, field)
        merged.update(data)
        class _Stub:
            pass

        stub = _Stub()
        for field in ADVISOR_SCORE_FIELDS:
            setattr(stub, field, merged.get(field, 0))
        validate_advisor_score_fields(stub)
        return data

    def get_student_full_name(self, obj):
        user = obj.internship.student.user
        return f"{user.first_name} {user.last_name}".strip() or user.username

    def get_student_id(self, obj):
        return obj.internship.student.student_id

    def get_advisor_name(self, obj):
        if obj.advisor:
            return obj.advisor.get_full_name() or obj.advisor.username
        return "Unknown"

    def get_company_name(self, obj):
        return obj.internship.position.company.company_name

    def get_workflow_status(self, obj):
        overall = getattr(obj.internship, "overall_evaluation", None)
        return overall.status if overall else "PENDING_ADVISOR"


class MonthlyIndustryEvaluationSerializer(serializers.ModelSerializer):
    student_full_name = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()

    class Meta:
        model = MonthlyIndustryEvaluation
        fields = [
            "id",
            "internship",
            "month_number",
            "student_full_name",
            "company_name",
            "submitted_at",
            "status",
            "advisor_reviewer",
            "advisor_approved_at",
            "advisor_rejected_at",
            "visible_to_student",
            "work_quality_score",
            "punctuality_score",
            "attitude_score",
            "initiative_score",
            "comments",
            "total_score",
            "form_data",
        ]
        read_only_fields = [
            "id",
            "submitted_at",
            "status",
            "advisor_reviewer",
            "advisor_approved_at",
            "advisor_rejected_at",
            "visible_to_student",
            "total_score",
        ]

    def validate(self, data):
        for field in [
            "work_quality_score",
            "punctuality_score",
            "attitude_score",
            "initiative_score",
        ]:
            val = data.get(field)
            if val is not None and not (0 <= val <= 5):
                raise serializers.ValidationError({field: "Must be between 0 and 5."})
        return data

    def get_student_full_name(self, obj):
        user = obj.internship.student.user
        return f"{user.first_name} {user.last_name}".strip() or user.username

    def get_company_name(self, obj):
        return obj.internship.position.company.company_name


class AdvisorApprovalSerializer(serializers.Serializer):
    """Optional comment when approving or rejecting an advisor evaluation."""

    comment = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class AdvisorQueueSerializer(serializers.Serializer):
    internship_id = serializers.IntegerField()
    student = serializers.DictField()
    company = serializers.CharField()
    timestamps = serializers.DictField()
    approval_stage = serializers.CharField()
    workflow_status = serializers.CharField()
    pending_logbooks_count = serializers.IntegerField()
    monthly_evaluations_count = serializers.IntegerField()
    monthly_reports_count = serializers.IntegerField(required=False)
    pending_monthly_evaluations = serializers.IntegerField(required=False)
    pending_documents = serializers.IntegerField(required=False)
    pending_final_evaluation = serializers.IntegerField(required=False)
    examiner_evaluations_submitted = serializers.IntegerField()
    examiner_evaluations_required = serializers.IntegerField()
    company_evaluation_submitted = serializers.BooleanField()
    final_evaluation_status = serializers.CharField(allow_null=True, required=False)
    advisor_evaluation_status = serializers.CharField(allow_null=True)
    final_report_status = serializers.CharField(allow_null=True)
    missing_requirements = serializers.ListField(child=serializers.CharField())
    documents = serializers.DictField(required=False)
    company_evaluations = serializers.DictField(required=False)
    examiner_evaluations = serializers.DictField(required=False)
    overall_evaluation = serializers.DictField(required=False)


class ExaminerEvaluationSerializer(serializers.ModelSerializer):
    student_full_name = serializers.SerializerMethodField()
    student_id = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    examiner_name = serializers.SerializerMethodField()
    weighted_score = serializers.DecimalField(
        max_digits=5, decimal_places=3, read_only=True
    )

    class Meta:
        model = ExaminerEvaluation
        fields = [
            "id",
            "internship",
            "student_full_name",
            "student_id",
            "company_name",
            "examiner",
            "examiner_name",
            "submitted_at",
            "technical_skills_score",
            "communication_score",
            "professionalism_score",
            "report_quality_score",
            "presentation_score",
            "comments",
            "total_score",
            "weighted_score",
            "form_data",
        ]
        read_only_fields = ["id", "examiner", "submitted_at", "total_score", "weighted_score"]

    def validate(self, data):
        for field in [
            "technical_skills_score",
            "communication_score",
            "professionalism_score",
            "report_quality_score",
            "presentation_score",
        ]:
            val = data.get(field)
            if val is not None and not (0 <= val <= 5):
                raise serializers.ValidationError({field: "Must be between 0 and 5."})
        return data

    def get_student_full_name(self, obj):
        user = obj.internship.student.user
        return f"{user.first_name} {user.last_name}".strip() or user.username

    def get_student_id(self, obj):
        return obj.internship.student.student_id

    def get_company_name(self, obj):
        try:
            return obj.internship.position.company.company_name
        except Exception:
            return ""

    def get_examiner_name(self, obj):
        if obj.examiner:
            return obj.examiner.get_full_name() or obj.examiner.username
        return ""


class OverallInternshipEvaluationSerializer(serializers.ModelSerializer):
    student_full_name = serializers.SerializerMethodField()
    can_finalize = serializers.SerializerMethodField()
    missing_requirements = serializers.SerializerMethodField()
    examiner_one_score = serializers.SerializerMethodField()
    examiner_two_score = serializers.SerializerMethodField()
    company_monthly_avg = serializers.SerializerMethodField()
    company_final_score = serializers.SerializerMethodField()
    advisor_evaluation_detail = AdvisorEvaluationSerializer(
        source="advisor_evaluation", read_only=True
    )

    class Meta:
        model = OverallInternshipEvaluation
        fields = [
            "id",
            "internship",
            "student_full_name",
            "status",
            "advisor_approved",
            "examiner_completed",
            "coordinator_approved",
            "examiner_approval_state",
            "visible_to_student",
            "advisor_score",
            "examiner_average_score",
            "examiner_one_score",
            "examiner_two_score",
            "company_score",
            "company_monthly_avg",
            "company_final_score",
            "final_total_score",
            "final_grade",
            "advisor_approved_at",
            "examiner_completed_at",
            "coordinator_approved_at",
            "coordinator_comment",
            "can_finalize",
            "missing_requirements",
            "advisor_evaluation_detail",
        ]
        read_only_fields = fields

    def get_student_full_name(self, obj):
        user = obj.internship.student.user
        return f"{user.first_name} {user.last_name}".strip() or user.username

    def get_can_finalize(self, obj):
        from core.services.evaluation_workflow import can_coordinator_finalize

        ok, _ = can_coordinator_finalize(obj)
        return ok

    def get_missing_requirements(self, obj):
        from core.services.evaluation_workflow import can_coordinator_finalize

        _, missing = can_coordinator_finalize(obj)
        return missing

    def get_examiner_one_score(self, obj):
        if obj.examiner_one_evaluation:
            form_data = obj.examiner_one_evaluation.form_data or {}
            final_mark = form_data.get("finalMark")
            if final_mark is not None:
                return float(final_mark)
            return float(obj.examiner_one_evaluation.weighted_score or 0)
        return 0

    def get_examiner_two_score(self, obj):
        if obj.examiner_two_evaluation:
            form_data = obj.examiner_two_evaluation.form_data or {}
            final_mark = form_data.get("finalMark")
            if final_mark is not None:
                return float(final_mark)
            return float(obj.examiner_two_evaluation.weighted_score or 0)
        return 0

    def get_company_monthly_avg(self, obj):
        return float(obj.company_monthly_avg or 0)

    def get_company_final_score(self, obj):
        return float(obj.company_final_score or 0)


class CoordinatorOverallApprovalSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])
    comment = serializers.CharField(required=False, allow_blank=True)


class ExaminerOverallApprovalSerializer(serializers.Serializer):
    slot = serializers.IntegerField(min_value=1, max_value=2)
