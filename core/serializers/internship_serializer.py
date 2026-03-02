from django.utils import timezone
from rest_framework import serializers,generics
from core.models import InternshipPosition,InternshipApplication,Skill

class InternshipApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = InternshipApplication
        fields = [
            'id',
            'position',
            'start_date',
            'end_date',
            'notes',
            'status',
            'created_at'
        ]
        read_only_fields = [
            'id',
            'status',  
            'created_at'  
        ]

    def validate(self, attrs):
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        request = self.context['request']
        student = request.user
        position = attrs.get('position')
        company = position.company

        if end_date <= start_date:
            raise serializers.ValidationError("End date must be after start date")

        if timezone.now().date() >= start_date:
            raise serializers.ValidationError("Start date must be in the future")

        existing = InternshipApplication.objects.filter(
            student=student,
            company=company,
            status__in=['PENDING', 'APPROVED', 'ONGOING']
        ).exists()
        if existing:
            raise serializers.ValidationError("You already have an active application for this company.")

        return attrs

    def create(self, validated_data):
        student = self.context['request'].user
        company = self.context['company']  # Passed from view
        internship = InternshipApplication.objects.create(
            student=student,
            company=company,
            status='PENDING',
            application_date=timezone.now(),
            **validated_data
        )
        return internship
    

class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ['id', 'name']    

class InternshipPositionSerializer(serializers.ModelSerializer):
    required_skills = serializers.PrimaryKeyRelatedField(
        queryset=Skill.objects.all(),
        many=True,
        required=False
    )

    class Meta:
        model = InternshipPosition
        fields = "__all__"
        read_only_fields = ("company", "created_at", "updated_at")