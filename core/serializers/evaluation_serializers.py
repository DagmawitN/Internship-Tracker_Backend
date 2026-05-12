from rest_framework import serializers
from core.models import FinalIndustryEvaluation, CompanyMentor, AdvisorEvaluation

class FinalIndustryEvaluationSerializer(serializers.ModelSerializer):
    """
    Serializer for Final Industry Evaluation submitted by company supervisors.
    Automatically calculates section totals and overall student performance.
    """
    student_full_name = serializers.SerializerMethodField()
    student_id = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    evaluator_name = serializers.SerializerMethodField()

    class Meta:
        model = FinalIndustryEvaluation
        fields = [
            'id',
            'internship',
            'student_full_name',
            'student_id',
            'company_name',
            'evaluator_name',
            'submitted_at',
            # Section A
            'knowledge_about_task',
            'problem_solving',
            'quality_of_work',
            'punctuality_in_production',
            'initiative',
            'section_a_total',
            # Section B
            'dedication',
            'cooperation',
            'discipline',
            'responsibility',
            'socialization',
            'communication',
            'decision_making',
            'section_b_total',
            # Section C
            'student_potential',
            'overall_comments',
            'would_offer_job',
            # Calculated
            'total_mark',
            'overall_student_performance',
        ]
        read_only_fields = [
            'id',
            'submitted_at',
            'section_a_total',
            'section_b_total',
            'total_mark',
            'overall_student_performance',
        ]

    def validate_score(self, value, field_name):
        """Validate individual scores are between 1-5."""
        if not (1 <= value <= 5):
            raise serializers.ValidationError(
                f"{field_name} must be between 1 and 5."
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
        """Validate internship exists and is completed."""
        if value.status != 'COMPLETED':
            raise serializers.ValidationError(
                "Internship must be completed to submit evaluation."
            )
        return value

    def validate(self, data):
        internship = data.get('internship')
        request = self.context.get('request')

        if internship is None:
            return data

        existing_evaluations = FinalIndustryEvaluation.objects.filter(internship=internship)
        if self.instance is not None:
            existing_evaluations = existing_evaluations.exclude(pk=self.instance.pk)

        if existing_evaluations.exists():
            raise serializers.ValidationError(
                "Final evaluation for this internship already exists."
            )

        if request is not None:
            user = getattr(request, 'user', None)
            if user is not None and user.is_authenticated:
                company_mentor = CompanyMentor.objects.filter(
                    user=user,
                    id=internship.mentor_id,
                ).first()
                if company_mentor is None:
                    raise serializers.ValidationError(
                        "Only the company mentor assigned to this internship can submit the evaluation."
                    )

        return data

    def get_student_full_name(self, obj):
        student = obj.internship.student
        user = student.user
        return f"{user.first_name} {user.last_name}".strip() or user.username

    def get_student_id(self, obj):
        return obj.internship.student.student_id

    def get_company_name(self, obj):
        return obj.internship.position.company.company_name

    def get_evaluator_name(self, obj):
        if obj.company_mentor:
            return obj.company_mentor.user.get_full_name() or obj.company_mentor.user.username
        return "Unknown"


class AdvisorEvaluationSerializer(serializers.ModelSerializer):
    """
    Serializer for Advisor Evaluation submitted by university advisors.
    Automatically calculates total and weighted scores.
    """
    student_full_name = serializers.SerializerMethodField()
    student_id = serializers.SerializerMethodField()
    advisor_name = serializers.SerializerMethodField()
    internship_id = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()

    class Meta:
        model = AdvisorEvaluation
        fields = [
            'id',
            'internship',
            'internship_id',
            'student_full_name',
            'student_id',
            'company_name',
            'advisor_name',
            'submitted_at',
            # Evaluation Scores
            'technical_followup_score',
            'communication_score',
            'attendance_followup_score',
            'professionalism_score',
            'report_quality_score',
            'comments',
            # Calculated Scores
            'total_score',
            'weighted_score',
        ]
        read_only_fields = [
            'id',
            'submitted_at',
            'total_score',
            'weighted_score',
        ]

    def validate_score(self, value, field_name):
        """Validate individual scores are between 1-5."""
        if not (1 <= value <= 5):
            raise serializers.ValidationError(
                f"{field_name} must be between 1 and 5."
            )
        return value

    def validate_technical_followup_score(self, value):
        return self.validate_score(value, "technical_followup_score")

    def validate_communication_score(self, value):
        return self.validate_score(value, "communication_score")

    def validate_attendance_followup_score(self, value):
        return self.validate_score(value, "attendance_followup_score")

    def validate_professionalism_score(self, value):
        return self.validate_score(value, "professionalism_score")

    def validate_report_quality_score(self, value):
        return self.validate_score(value, "report_quality_score")

    def validate_internship(self, value):
        """Validate internship exists."""
        if value is None:
            raise serializers.ValidationError("Internship is required.")
        return value

    def validate(self, data):
        """Validate no existing evaluation and advisor authorization."""
        internship = data.get('internship')
        request = self.context.get('request')

        if internship is None:
            return data

        # Check for existing evaluation
        existing_evaluations = AdvisorEvaluation.objects.filter(internship=internship)
        if self.instance is not None:
            existing_evaluations = existing_evaluations.exclude(pk=self.instance.pk)

        if existing_evaluations.exists():
            raise serializers.ValidationError(
                "Advisor evaluation for this internship already exists."
            )

        # Validate advisor is assigned to this internship
        if request is not None:
            user = getattr(request, 'user', None)
            if user is not None and user.is_authenticated:
                from core.models import AdvisorAssignment
                is_assigned = AdvisorAssignment.objects.filter(
                    internship=internship,
                    advisor=user,
                ).exists()
                if not is_assigned:
                    raise serializers.ValidationError(
                        "Only the advisor assigned to this internship can submit the evaluation."
                    )

        return data

    def get_student_full_name(self, obj):
        student = obj.internship.student
        user = student.user
        return f"{user.first_name} {user.last_name}".strip() or user.username

    def get_student_id(self, obj):
        return obj.internship.student.student_id

    def get_advisor_name(self, obj):
        if obj.advisor:
            return obj.advisor.get_full_name() or obj.advisor.username
        return "Unknown"

    def get_internship_id(self, obj):
        return obj.internship.id

    def get_company_name(self, obj):
        return obj.internship.position.company.company_name

