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


class FinalReportDetailSerializer(serializers.ModelSerializer):
    student_full_name = serializers.SerializerMethodField()
    student_id = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    file_urls = serializers.SerializerMethodField()
    examiner_reviewer_name = serializers.SerializerMethodField()
    advisor_comment_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = [
            "id",
            "internship",
            "title",
            "status",
            "submission_date",
            "student_full_name",
            "student_id",
            "company_name",
            "file_urls",
            "examiner_reviewer",
            "examiner_reviewer_name",
            "examiner_approved_at",
            "examiner_rejected_at",
            "advisor_comment",
            "advisor_comment_by",
            "advisor_comment_by_name",
            "advisor_comment_at",
            "reviewed_at",
            "approved_at",
            "rejected_at",
        ]
        read_only_fields = fields

    def get_student_full_name(self, obj):
        user = obj.internship.student.user
        return f"{user.first_name} {user.last_name}".strip() or user.username

    def get_student_id(self, obj):
        return obj.internship.student.student_id

    def get_company_name(self, obj):
        return obj.internship.position.company.company_name

    def get_file_urls(self, obj):
        return [f.file.url for f in obj.files.all() if f.file]

    def get_examiner_reviewer_name(self, obj):
        if obj.examiner_reviewer:
            return obj.examiner_reviewer.get_full_name() or obj.examiner_reviewer.username
        return None

    def get_advisor_comment_by_name(self, obj):
        if obj.advisor_comment_by:
            return obj.advisor_comment_by.get_full_name() or obj.advisor_comment_by.username
        return None


class AdvisorFinalReportCommentSerializer(serializers.Serializer):
    comment = serializers.CharField(required=True, allow_blank=False, max_length=5000)


class AdvisorFinalReportListSerializer(FinalReportDetailSerializer):
    class Meta(FinalReportDetailSerializer.Meta):
        fields = [
            "id",
            "title",
            "status",
            "submission_date",
            "student_full_name",
            "student_id",
            "company_name",
            "file_urls",
            "examiner_approved_at",
            "examiner_rejected_at",
            "advisor_comment",
            "advisor_comment_at",
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
    internship_id = serializers.IntegerField(source="internship.id", read_only=True)

    class Meta:
        model = WeeklyLogbook
        fields = [
            'id',
            'week_number',
            'status',
            'student_full_name',
            'student_id',
            'internship_id',
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


class StudentInternshipDocumentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    file_name = serializers.SerializerMethodField()
    submitted_at = serializers.DateTimeField(source="submission_date", read_only=True)
    description = serializers.SerializerMethodField()
    internship_id = serializers.IntegerField(source="internship.id", read_only=True)
    student_id = serializers.CharField(source="internship.student.student_id", read_only=True)
    student_full_name = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    advisor_name = serializers.SerializerMethodField()
    examiner_name = serializers.SerializerMethodField()
    examiner2_name = serializers.SerializerMethodField()
    advisor_status = serializers.SerializerMethodField()
    examiner_status = serializers.SerializerMethodField()
    advisor_comment = serializers.CharField(read_only=True)
    examiner_comment = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = [
            "id",
            "title",
            "description",
            "status",
            "submitted_at",
            "internship_id",
            "student_id",
            "student_full_name",
            "company_name",
            "advisor_name",
            "examiner_name",
            "examiner2_name",
            "file_url",
            "file_name",
            "advisor_status",
            "examiner_status",
            "advisor_comment",
            "examiner_comment",
        ]

    def get_student_full_name(self, obj):
        user = obj.internship.student.user
        return f"{user.first_name} {user.last_name}".strip() or user.username

    def get_company_name(self, obj):
        return obj.internship.position.company.company_name

    def get_advisor_name(self, obj):
        advisor_profile = getattr(obj.internship.student, "advisor", None)
        if advisor_profile and advisor_profile.user:
            u = advisor_profile.user
            return f"{u.first_name} {u.last_name}".strip() or u.username
        return ""

    def _get_examiner_names(self, obj):
        from core.models import AdvisorAssignment

        assignments = (
            AdvisorAssignment.objects.filter(
                internship=obj.internship,
                role="EXAMINER",
            )
            .select_related("advisor")
            .order_by("assigned_at")[:2]
        )
        names = []
        for a in assignments:
            u = a.advisor
            if not u:
                continue
            names.append(f"{u.first_name} {u.last_name}".strip() or u.username)
        while len(names) < 2:
            names.append("")
        return names

    def get_examiner_name(self, obj):
        return self._get_examiner_names(obj)[0]

    def get_examiner2_name(self, obj):
        return self._get_examiner_names(obj)[1]

    def get_file_url(self, obj):
        f = obj.files.first()
        return f.file.url if f and f.file else ""

    def get_file_name(self, obj):
        f = obj.files.first()
        return f.file_name if f else ""

    def get_description(self, obj):
        fb = obj.feedbacks.first()
        return fb.feedback_text if fb else ""

    def get_advisor_status(self, obj):
        status = str(obj.status or "").upper()
        if status == "ADVISOR_APPROVED":
            return "APPROVED"
        if status in {"ADVISOR_REJECTED", "REJECTED"}:
            return "REJECTED"
        return "PENDING"

    def get_examiner_status(self, obj):
        status = str(obj.status or "").upper()
        if status == "EXAMINER_APPROVED":
            return "APPROVED"
        if status == "EXAMINER_REJECTED":
            return "REJECTED"
        return "PENDING"

    def get_examiner_comment(self, obj):
        # No dedicated examiner comment field yet for OTHER report type.
        return ""


