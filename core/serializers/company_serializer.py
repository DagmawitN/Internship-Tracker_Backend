from rest_framework import serializers
from core.models import Company,InternshipApplication

class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = [
            'id',
            'company_name',
            'industry_type',
            'address',
            'contact_email',
            'contact_phone',
            'website',
            'is_active',
            'created_at',
        ]
        read_only_fields = fields

class CompanyApplicationSerializer(serializers.ModelSerializer):
    position_title = serializers.CharField(source = 'position.title', read_only = True)
    student_email = serializers.EmailField(source='student.user.email', read_only=True)

    class Meta:
        model = InternshipApplication
        fields = [
            'id',
            'position_title',
            'student_email',
            'dept_status',
            'mentor_status',
            'student_decision',
            'created_at'
        ]
