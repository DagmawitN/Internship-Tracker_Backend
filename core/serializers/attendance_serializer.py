from rest_framework import serializers

from core.models import Attendance


class CheckInSerializer(serializers.Serializer):
    internship_id = serializers.IntegerField()
    latitude = serializers.FloatField(required=False, allow_null=True)
    longitude = serializers.FloatField(required=False, allow_null=True)
    accuracy = serializers.FloatField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class CheckOutSerializer(serializers.Serializer):
    internship_id = serializers.IntegerField()


class AttendanceNotesSerializer(serializers.Serializer):
    notes = serializers.CharField(allow_blank=True)


class AttendanceSerializer(serializers.ModelSerializer):
    internship_id = serializers.IntegerField(source="internship.id", read_only=True)
    position_title = serializers.CharField(
        source="internship.position.title", read_only=True
    )
    student_email = serializers.EmailField(
        source="internship.student.user.email", read_only=True
    )

    class Meta:
        model = Attendance
        fields = [
            "id",
            "internship_id",
            "position_title",
            "student_email",
            "date",
            "check_in_time",
            "check_out_time",
            "total_hours",
            "status",
            "notes",
            "latitude",
            "longitude",
            "accuracy",
            "is_location_verified",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
