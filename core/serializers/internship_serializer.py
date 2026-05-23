from rest_framework import serializers

from core.models import Internship, InternshipApplication, InternshipPosition, Skill


class InternshipApplicationSerializer(serializers.ModelSerializer):
    requested_start_date = serializers.DateField(required=False, allow_null=True)
    requested_end_date = serializers.DateField(required=False, allow_null=True)
    working_days_per_week = serializers.IntegerField(
        required=False, allow_null=True, min_value=1, max_value=7
    )
    working_hours_per_day = serializers.DecimalField(
        required=False, allow_null=True, max_digits=4, decimal_places=1
    )

    class Meta:
        model = InternshipApplication
        fields = [
            "id",
            "position",
            "dept_status",
            "mentor_status",
            "student_decision",
            "requested_start_date",
            "requested_end_date",
            "working_days_per_week",
            "working_hours_per_day",
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
        accepted = getattr(obj, "accepted_applications", 0) or 0
        return max(obj.max_applicants - accepted, 0)

    def validate_working_days(self, value):
        valid = {
            "MONDAY",
            "TUESDAY",
            "WEDNESDAY",
            "THURSDAY",
            "FRIDAY",
            "SATURDAY",
            "SUNDAY",
        }
        for day in value:
            if day.upper() not in valid:
                raise serializers.ValidationError(
                    f"'{day}' is not a valid weekday name."
                )
        return [d.upper() for d in value]


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


class InternshipRecordSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for the Internship execution model.
    Exposes denormalized fields useful for list/search views.
    """

    student_id = serializers.CharField(source="student.student_id", read_only=True)
    student_name = serializers.SerializerMethodField()
    student_email = serializers.EmailField(source="student.user.email", read_only=True)
    department = serializers.CharField(
        source="student.department.department_name", read_only=True
    )
    position_title = serializers.CharField(source="position.title", read_only=True)
    company_name = serializers.SerializerMethodField()
    mentor_name = serializers.SerializerMethodField()
    advisor = serializers.SerializerMethodField()
    work_mode = serializers.SerializerMethodField()

    class Meta:
        model = Internship
        fields = [
            "id",
            "student_id",
            "student_name",
            "student_email",
            "department",
            "position_title",
            "company_name",
            "mentor_name",
            "advisor",
            "work_mode",
            "status",
            "start_date",
            "end_date",
            "total_hours",
            "notes",
        ]
        read_only_fields = fields

    def get_student_name(self, obj):
        u = obj.student.user
        return u.get_full_name().strip() or u.username

    def get_company_name(self, obj):
        return (
            obj.company.company_name
            if obj.company
            else (obj.position.company.company_name if obj.position else None)
        )

    def get_mentor_name(self, obj):
        if obj.mentor and obj.mentor.user:
            u = obj.mentor.user
            return u.get_full_name().strip() or u.username
        return None

    def get_advisor(self, obj):
        adv = obj.student.advisor
        if not adv:
            return None
        u = adv.user
        return {
            "id": adv.id,
            "name": u.get_full_name().strip() or u.username,
            "email": u.email,
        }

    def get_work_mode(self, obj):
        return getattr(obj.position, "work_mode", None)


class StudentApplicationSerializer(serializers.ModelSerializer):
    """Read-only serializer for GET /applications/my/."""

    position_title = serializers.CharField(source="position.title", read_only=True)
    company_name = serializers.CharField(
        source="position.company.company_name", read_only=True
    )
    overall_status = serializers.CharField(read_only=True)
    advisor_name = serializers.SerializerMethodField()
    applied_at = serializers.DateTimeField(source="created_at", read_only=True)
    resume_url = serializers.SerializerMethodField()

    class Meta:
        model = InternshipApplication
        fields = [
            "id",
            "position",
            "position_title",
            "company_name",
            "dept_status",
            "mentor_status",
            "advisor_status",
            "student_decision",
            "overall_status",
            "rejection_reason",
            "requested_start_date",
            "requested_end_date",
            "working_days_per_week",
            "working_hours_per_day",
            "coordinator_signature",
            "coordinator_signed_at",
            "mentor_signature",
            "mentor_signed_at",
            "form_snapshot",
            "advisor_name",
            "applied_at",
            "resume_url",
        ]
        read_only_fields = fields

    def get_advisor_name(self, obj):
        if obj.advisor and obj.advisor.user:
            u = obj.advisor.user
            return u.get_full_name().strip() or u.username
        return None

    def get_resume_url(self, obj):
        student = obj.student
        if student.resume:
            try:
                return student.resume.url
            except Exception:
                return None
        return None


class InternshipRequestFormSerializer(serializers.ModelSerializer):
    """
    Full internship request form — used by coordinators and mentors to
    view all application details including snapshot and signature status.
    """

    position_title = serializers.CharField(source="position.title", read_only=True)
    company_name = serializers.CharField(
        source="position.company.company_name", read_only=True
    )
    work_mode = serializers.CharField(source="position.work_mode", read_only=True)
    overall_status = serializers.CharField(read_only=True)
    student_name = serializers.SerializerMethodField()
    student_email = serializers.EmailField(source="student.user.email", read_only=True)
    resume_url = serializers.SerializerMethodField()

    class Meta:
        model = InternshipApplication
        fields = [
            "id",
            "student_name",
            "student_email",
            "position_title",
            "company_name",
            "work_mode",
            "overall_status",
            "dept_status",
            "mentor_status",
            "advisor_status",
            "student_decision",
            "rejection_reason",
            "requested_start_date",
            "requested_end_date",
            "working_days_per_week",
            "working_hours_per_day",
            "coordinator_signature",
            "coordinator_signed_at",
            "mentor_signature",
            "mentor_signed_at",
            "form_snapshot",
            "resume_url",
            "created_at",
        ]
        read_only_fields = fields

    def get_student_name(self, obj):
        u = obj.student.user
        return u.get_full_name().strip() or u.username

    def get_resume_url(self, obj):
        student = obj.student
        if student.resume:
            try:
                return student.resume.url
            except Exception:
                return None
        return None
