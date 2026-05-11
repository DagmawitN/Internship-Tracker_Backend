from rest_framework import serializers
from core.models import WeeklyLogbook, DailyLogEntry, Report, ReportFile

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

