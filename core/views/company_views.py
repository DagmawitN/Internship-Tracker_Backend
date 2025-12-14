from rest_framework import generics, permissions,status
from rest_framework.response import Response
from core.models import Internship, Company
from django.contrib.auth import get_user_model
from core.serializers.company_serializer import CompanySerializer
from django_filters.rest_framework import DjangoFilterBackend


User = get_user_model()

class CompanyApplicantsListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        # Assume company user has one company
        company = getattr(request.user, 'company_profile', None)
        if not company:
            return Response({'error': 'You are not associated with any company.'}, status=403)

        # Get pending applicants
        internships = Internship.objects.filter(company=company, status='PENDING')
        data = [
            {
                'internship_id': i.id,
                'student_id': i.student.student_profile.student_id,
                'student_name': i.student.full_name(),
                'department': i.student.student_profile.department.department_name,
                'application_date': i.application_date,
                'status': i.status
            } for i in internships
        ]
        return Response({'applicants': data})



class CompanyApplicantActionView(generics.UpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Internship.objects.all()
    lookup_field = 'id'  # internship id

    def patch(self, request, *args, **kwargs):
        internship = self.get_object()

        # Check if the internship belongs to the company
        company = getattr(request.user, 'company_profile', None)
        if internship.company != company:
            return Response({'error': 'You cannot modify this application.'}, status=403)

        action = request.data.get('action', '').lower()
        if action not in ['approve', 'reject']:
            return Response({'error': 'Action must be "approve" or "reject".'}, status=400)

        internship.status = 'APPROVED' if action == 'approve' else 'REJECTED'
        internship.save()

        return Response({
            'message': f'Applicant {action}d successfully',
            'internship_id': internship.id,
            'status': internship.status
        }, status=status.HTTP_200_OK)

class VerifiedCompaniesListView(generics.ListAPIView):

    permission_classes = [permissions.IsAuthenticated]
    queryset = Company.objects.filter(is_active = True)
    serializer_class = CompanySerializer 

    filter_backends = ['DjangoFilterBackend','SearchFilter', 'OrderingFilter']
    search_fields = ['company_name','industry_type']
    ordering_fields = ['created_at','company_name','industry_type']
    ordering = ['company_name']

