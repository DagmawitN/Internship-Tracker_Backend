from datetime import timezone
from rest_framework import serializers
from core.models import Internship

class InternshipApplicationSerializer (serializers.ModelSerializer):
    class Meta:
        model = Internship
        fields = [
            'id',
            'company',
            'start_date',
            'end_date',
            'notes',
            'status',
            'application_date'
        ]
        read_only_fields = [
            'id',
            'company',  # Company is set by the view (from URL)
            'status',  # Always PENDING when first applied
            'application_date'  # Always set to now()
        ]
    def validate(self, attrs):
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        company = attrs.get('company')

        if end_date <= start_date:
            raise serializers.ValidationError(
                "End date must be after start date"
            )
            
        today = timezone.now().date()
        if today >= start_date:
            raise serializers.ValidationError(
                "Start date must be in the future"
            )
        student = self.context['request'].user
        existing = Internship.objects.filter(
            student = student,
            company = company,
            status__in = ['PENDING', 'APPROVED', 'ONGOING']
        ).exists
        if existing:
            raise serializers.ValidationError(
                "You already have an active application for this company."
            )
        return attrs
    def create(self, validated_data):
        student = self.context["request"].user
        internship = Internship.create(
            student = student,
            status = 'PENDING',
            application_date = timezone.now(),
            **validated_data
        )
        return internship