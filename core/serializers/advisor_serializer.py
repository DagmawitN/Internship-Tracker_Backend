from rest_framework import serializers

from core.models import Advisor, Student


class AssignAdvisorSerializer(serializers.Serializer):
    advisor_id = serializers.IntegerField(
        help_text="User ID of the staff member to assign as advisor"
    )


class AssignExaminerSerializer(serializers.Serializer):
    examiner_id = serializers.IntegerField(
        help_text="User ID of the staff member to assign as examiner"
    )


class AdvisorReviewSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class AdvisorNotesSerializer(serializers.Serializer):
    notes = serializers.CharField(allow_blank=True)
    mode = serializers.ChoiceField(
        choices=["append", "overwrite"], required=False, default="append"
    )


class AdvisorSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_name = serializers.SerializerMethodField()
    department_name = serializers.CharField(
        source="department.department_name", read_only=True
    )
    assigned_students_count = serializers.SerializerMethodField()

    class Meta:
        model = Advisor
        fields = [
            "id",
            "user_email",
            "user_name",
            "department_name",
            "assigned_students_count",
            "created_at",
        ]
        read_only_fields = fields

    def get_user_name(self, obj):
        u = obj.user
        full = u.get_full_name()
        return full if full.strip() else u.username

    def get_assigned_students_count(self, obj):
        return obj.assigned_students.count()
