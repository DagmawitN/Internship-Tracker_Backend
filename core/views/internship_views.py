from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from core.models import Internship, Company
from core.serializers.internship_serializer import InternshipApplicationSerializer
from core.permissions import IsStudentUser

class InternshipApplicationView(generics.CreateAPIView):
    queryset = Internship.objects.all()
    serializer_class = InternshipApplicationSerializer
    permission_classes = [IsAuthenticated,IsStudentUser]

    def get_company(self):
        company_id = self.kwargs.get('company_id')
        company = get_object_or_404(Company,id = company_id)
        return company
    
    def validate_company(self,company):
        if not company.is_active:
            return Response(
                {"detail": "This company is not verified and cannot accept applications."},
                status=status.HTTP_400_BAD_REQUEST
            )
        return None

    def create(self, request, *args, **kwargs):
        company = self.get_company()
        validation_response = self.validate_company(company)

        if validation_response:
            return validation_response
        
        serializer = self.get_serializer(data = request.data)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data['company'] = company
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers
        )



