from rest_framework import serializers
from core.models import Company

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
        