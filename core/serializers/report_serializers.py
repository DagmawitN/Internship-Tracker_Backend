from rest_framework import serializers
from core.models import WeeklyLogbook, DailyLogEntry, Report, ReportFile, FinalIndustryEvaluation

class DailyLogEntrySerializer(serializers.ModelSerializer):

    class Meta:
        model = DailyLogEntry
        fields = [
            "id",
            "day_number",
            "work_date",
            "work_performed",
        ]

class WeeklyLogbookSerializer(serializers.ModelSerializer):

    daily_entries = DailyLogEntrySerializer(
        many=True,
        read_only=True
    )

    class Meta:
        model = WeeklyLogbook
        fields = [
            "id",
            "week_number",
            "status",
            "student_comment",
            "company_comment",
            "advisor_comment",
            "submitted_at",
            "verified_at",
            "reviewed_at",
            "daily_entries",
        ]

        read_only_fields = [
            "status",
            "company_comment",
            "advisor_comment",
            "submitted_at",
            "verified_at",
            "reviewed_at",
        ]

class SubmitFinalReportSerializer(serializers.ModelSerializer):
    file = serializers.FileField(required=True)

    class Meta:
        model = Report
        fields = ['title', 'file']

    def validate_file(self, value):
        # Validate file type: only PDF, DOC, DOCX
        allowed_types = [
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        ]
        if value.content_type not in allowed_types:
            raise serializers.ValidationError("Only PDF, DOC, and DOCX files are allowed.")
        return value

    def create(self, validated_data):
        file = validated_data.pop('file')
        report = super().create(validated_data)
        # Create ReportFile
        ReportFile.objects.create(
            report=report,
            file=file,
            file_name=file.name,
            file_size=file.size,
            mime_type=file.content_type
        )
        return report


class AdvisorFinalReportListSerializer(serializers.ModelSerializer):
    student_full_name = serializers.SerializerMethodField()
    student_id = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    file_urls = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = [
            'id',
            'title',
            'status',
            'submission_date',
            'student_full_name',
            'student_id',
            'company_name',
            'file_urls',
        ]

    def get_student_full_name(self, obj):
        student = obj.internship.student
        user = student.user
        return f"{user.first_name} {user.last_name}".strip() or user.username

    def get_student_id(self, obj):
        return obj.internship.student.student_id

    def get_company_name(self, obj):
        return obj.internship.position.company.company_name

    def get_file_urls(self, obj):
        return [file.file.url for file in obj.files.all()]


class AdvisorWeeklyLogbookSerializer(serializers.ModelSerializer):
    """
    Serializer for advisors to view weekly logbooks submitted by assigned students.
    """
    student_full_name = serializers.SerializerMethodField()
    student_id = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    daily_log_entries = serializers.SerializerMethodField()

    class Meta:
        model = WeeklyLogbook
        fields = [
            'id',
            'week_number',
            'status',
            'student_full_name',
            'student_id',
            'company_name',
            'submitted_at',
            'company_comment',
            'daily_log_entries',
        ]

    def get_student_full_name(self, obj):
        student = obj.internship.student
        user = student.user
        return f"{user.first_name} {user.last_name}".strip() or user.username

    def get_student_id(self, obj):
        return obj.internship.student.student_id

    def get_company_name(self, obj):
        return obj.internship.position.company.company_name

    def get_daily_log_entries(self, obj):
        entries = obj.daily_entries.all().order_by('day_number')
        return DailyLogEntrySerializer(entries, many=True).data


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
        """Validate internship exists and is completed or ongoing."""
        if value.status not in ['COMPLETED', 'ONGOING']:
            raise serializers.ValidationError(
                "Internship must be completed or ongoing to submit evaluation."
            )
        return value

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

