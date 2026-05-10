from rest_framework import serializers

from core.models import Internship, InternshipApplication, InternshipPosition, Skill


class InternshipApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = InternshipApplication
        fields = [
            "id",
            "position",
            "dept_status",
            "mentor_status",
            "student_decision",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "dept_status",
            "mentor_status",
            "student_decision",
            "position",
            "created_at",
        ]

    def validate(self, attrs):
        request = self.context["request"]
        user = request.user

        try:
            student = user.student_profile
        except:
            raise serializers.ValidationError("User is not a student.")

        attrs["student"] = student

        # Duplicate application prevention is handled in the view using (student, position),
        # because `position` is read-only here and provided via the URL.

        return attrs

    def create(self, validated_data):
        return InternshipApplication.objects.create(**validated_data)


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ["id", "name"]


class InternshipPositionSerializer(serializers.ModelSerializer):
    required_skills = serializers.PrimaryKeyRelatedField(
        queryset=Skill.objects.all(), many=True, required=False
    )
    accepted_applications = serializers.IntegerField(read_only=True)
    available_slots = serializers.SerializerMethodField()

    class Meta:
        model = InternshipPosition
        fields = "__all__"
        read_only_fields = ("company", "created_at", "updated_at")

    def get_available_slots(self, obj):
        if obj.max_applicants is None:
            return None
        accepted = getattr(obj, "accepted_applications", 0)
        return max(obj.max_applicants - accepted, 0)


class InternshipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Internship
        fields = "__all__"
        read_only_fields = (
            "student",
            "position",
            "company",
            "supervisor",
            "mentor",
            "status",
            "end_date",
            "total_hours",
        )


class InternshipNotesSerializer(serializers.Serializer):
    notes = serializers.CharField(allow_blank=True)
    mode = serializers.ChoiceField(
        choices=["append", "overwrite"], required=False, default="append"
    )
