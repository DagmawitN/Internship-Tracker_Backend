from rest_framework import serializers

from core.models import SelfPlacementRequest


class SelfPlacementRequestSerializer(serializers.ModelSerializer):
    student_id = serializers.CharField(source="student.student_id", read_only=True)
    student_name = serializers.SerializerMethodField()
    submitted_at = serializers.DateTimeField(source="created_at", read_only=True)
    company_license_url = serializers.SerializerMethodField()

    class Meta:
        model = SelfPlacementRequest
        fields = [
            "id",
            "student_id",
            "student_name",
            "company_name",
            "representative_name",
            "representative_email",
            "representative_phone",
            "location",
            "company_license",
            "company_license_url",
            "additional_notes",
            "status",
            "review_notes",
            "reviewed_at",
            "submitted_at",
        ]
        read_only_fields = [
            "id",
            "student_id",
            "student_name",
            "status",
            "review_notes",
            "reviewed_at",
            "submitted_at",
            "company_license_url",
        ]

    def get_student_name(self, obj):
        user = obj.student.user
        return user.get_full_name().strip() or user.username

    def get_company_license_url(self, obj):
        try:
            return obj.company_license.url if obj.company_license else None
        except Exception:
            return None