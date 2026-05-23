from rest_framework import serializers

from core.models import Company, InternshipApplication


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = [
            "id",
            "company_name",
            "industry_type",
            "address",
            "contact_email",
            "contact_phone",
            "website",
            "is_active",
            "created_at",
        ]
        read_only_fields = fields


class CompanyApplicationSerializer(serializers.ModelSerializer):
    position_title = serializers.CharField(source="position.title", read_only=True)
    student_email = serializers.EmailField(source="student.user.email", read_only=True)
    student_name = serializers.SerializerMethodField()
    overall_status = serializers.SerializerMethodField()
    resume_url = serializers.SerializerMethodField()

    class Meta:
        model = InternshipApplication
        fields = [
            "id",
            "position_title",
            "student_email",
            "student_name",
            "dept_status",
            "mentor_status",
            "student_decision",
            "overall_status",
            "rejection_reason",
            "requested_start_date",
            "requested_end_date",
            "working_days_per_week",
            "working_hours_per_day",
            "form_snapshot",
            "resume_url",
            "created_at",
        ]
        read_only_fields = fields

    def get_student_name(self, obj):
        u = obj.student.user
        return u.get_full_name().strip() or u.username

    def get_overall_status(self, obj):
        return obj.overall_status

    def get_resume_url(self, obj):
        student = obj.student
        if student.resume:
            try:
                return student.resume.url
            except Exception:
                return None
        return None
