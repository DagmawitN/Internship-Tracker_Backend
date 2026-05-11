from rest_framework import generics, serializers
from rest_framework.permissions import IsAuthenticated
from core.models import FinalIndustryEvaluation, CompanyMentor, AdvisorAssignment
from core.serializers.report_serializers import FinalIndustryEvaluationSerializer


class FinalIndustryEvaluationListCreateAPIView(generics.ListCreateAPIView):
    """
    API endpoint for company supervisors to submit and view final industry evaluations.
    POST: Create a new final industry evaluation
    GET: List all final industry evaluations
    """
    permission_classes = [IsAuthenticated]
    serializer_class = FinalIndustryEvaluationSerializer
    
    def get_queryset(self):
        """
        Filter evaluations based on user role:
        - Company mentors see their own evaluations
        - Advisors see all evaluations for their assigned students
        """
        user = self.request.user
        
        # Check if user is a company mentor
        try:
            company_mentor = CompanyMentor.objects.get(user=user)
            return FinalIndustryEvaluation.objects.filter(
                company_mentor=company_mentor
            ).select_related(
                'internship__student__user',
                'internship__position__company',
                'company_mentor__user'
            )
        except CompanyMentor.DoesNotExist:
            pass
        
        # Check if user is an advisor
        if hasattr(user, 'role') and user.role.role_name == 'Advisor':
            assigned_internships = AdvisorAssignment.objects.filter(
                advisor=user
            ).values_list('internship', flat=True)
            
            return FinalIndustryEvaluation.objects.filter(
                internship__in=assigned_internships
            ).select_related(
                'internship__student__user',
                'internship__position__company',
                'company_mentor__user'
            )
        
        # Default: no access
        return FinalIndustryEvaluation.objects.none()
    
    def perform_create(self, serializer):
        """
        Ensure only company mentors can create evaluations and validate permissions.
        """
        # Get company mentor
        try:
            company_mentor = CompanyMentor.objects.get(user=self.request.user)
        except CompanyMentor.DoesNotExist:
            raise serializers.ValidationError(
                "Only company supervisors/mentors can submit evaluations."
            )
        
        # Get internship
        internship = serializer.validated_data.get('internship')
        
        # Verify mentor is assigned to this internship
        if internship.mentor != company_mentor:
            raise serializers.ValidationError(
                "You can only evaluate internships assigned to you."
            )
        
        # Check if evaluation already exists
        if FinalIndustryEvaluation.objects.filter(internship=internship).exists():
            raise serializers.ValidationError(
                "Final evaluation for this internship already exists."
            )
        
        # Save with company mentor
        serializer.save(company_mentor=company_mentor)


class FinalIndustryEvaluationDetailAPIView(generics.RetrieveUpdateAPIView):
    """
    API endpoint to retrieve or update a specific final industry evaluation.
    GET: Retrieve evaluation details
    PUT/PATCH: Update evaluation
    """
    permission_classes = [IsAuthenticated]
    serializer_class = FinalIndustryEvaluationSerializer
    lookup_field = 'id'
    
    def get_queryset(self):
        """Filter evaluations for authorized users."""
        user = self.request.user
        
        # Check if user is a company mentor
        try:
            company_mentor = CompanyMentor.objects.get(user=user)
            return FinalIndustryEvaluation.objects.filter(
                company_mentor=company_mentor
            ).select_related(
                'internship__student__user',
                'internship__position__company',
                'company_mentor__user'
            )
        except CompanyMentor.DoesNotExist:
            pass
        
        # Check if user is an advisor
        if hasattr(user, 'role') and user.role.role_name == 'Advisor':
            assigned_internships = AdvisorAssignment.objects.filter(
                advisor=user
            ).values_list('internship', flat=True)
            
            return FinalIndustryEvaluation.objects.filter(
                internship__in=assigned_internships
            ).select_related(
                'internship__student__user',
                'internship__position__company',
                'company_mentor__user'
            )
        
        return FinalIndustryEvaluation.objects.none()
    
    def perform_update(self, serializer):
        """Only company mentors can update their own evaluations."""
        evaluation = self.get_object()
        
        # Verify user is the company mentor who submitted this
        try:
            company_mentor = CompanyMentor.objects.get(user=self.request.user)
            if evaluation.company_mentor != company_mentor:
                raise serializers.ValidationError(
                    "You can only update your own evaluations."
                )
        except CompanyMentor.DoesNotExist:
            raise serializers.ValidationError(
                "Only company supervisors/mentors can update evaluations."
            )
        
        serializer.save()
