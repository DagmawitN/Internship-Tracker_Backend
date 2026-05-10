from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions,status
from rest_framework.response import Response
from core.models import InternshipApplication, Company, CompanyMentor
from django.contrib.auth import get_user_model
from core.serializers.company_serializer import CompanySerializer,CompanyApplicationSerializer
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.views import APIView
from core.permissions import IsCompanyMentor,IsMentorOfCompany
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError


User = get_user_model()

from rest_framework import serializers

class ActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=[("accept", "Accept"), ("reject", "Reject")])

class CompanyApplicantsListView(generics.ListAPIView):
    serializer_class = CompanyApplicationSerializer
    permission_classes = [permissions.IsAuthenticated, IsCompanyMentor, IsMentorOfCompany]

    def get_queryset(self):
        company_id = self.kwargs['company_id']
        mentor = CompanyMentor.objects.filter(
            user=self.request.user,
            company_id=company_id
        ).first()
        if not mentor:
            raise PermissionDenied("You can only view applicants for your company.")

        queryset = InternshipApplication.objects.filter(position__company_id=mentor.company_id)

        dept_status = self.request.query_params.get("dept_status")
        mentor_status = self.request.query_params.get("mentor_status")
        student_decision = self.request.query_params.get("student_decision")

        # Backwards-compatible alias; in company context "status" usually means mentor_status
        status_alias = self.request.query_params.get("status")
        if status_alias and not mentor_status:
            mentor_status = status_alias

        if dept_status:
            queryset = queryset.filter(dept_status=dept_status.strip().upper())
        if mentor_status:
            queryset = queryset.filter(mentor_status=mentor_status.strip().upper())
        if student_decision:
            queryset = queryset.filter(student_decision=student_decision.strip().upper())
        return queryset

class CompanyApplicantActionView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ActionSerializer

    def patch(self, request, *args, **kwargs):
        application = get_object_or_404(InternshipApplication, id=kwargs["id"])

        mentor = CompanyMentor.objects.filter(user=request.user).first()
        if not mentor:
            raise PermissionDenied("Only company mentors can modify applications.")

        # Ensure application belongs to mentor's company
        if application.position.company_id != mentor.company_id:
            raise PermissionDenied("You cannot modify this application.")

        if application.dept_status != "APPROVED":
            raise ValidationError("Application not approved by department.")

        action = request.data.get('action', '').lower()
        if action not in ['accept', 'reject']:
            raise ValidationError('Action must be "accept" or "reject".')

        if application.mentor_status not in [None, "PENDING"]:
            raise ValidationError("Already reviewed by mentor.")

        if action == "accept":
            application.mentor_status = "ACCEPTED"
            application.mentor = mentor
        else:
            application.mentor_status = "REJECTED"

        application.save()

        return Response({
            'message': "Mentor decision recorded",
            'application_id': application.id,
            'mentor_status': application.mentor_status,
        }, status=status.HTTP_200_OK)

class VerifiedCompaniesListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Company.objects.filter(is_active=True)
    serializer_class = CompanySerializer

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['company_name','industry_type']
    ordering_fields = ['created_at','company_name','industry_type']
    ordering = ['company_name']

class MentorReviewView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyMentor]
    serializer_class = ActionSerializer

    def patch(self, request, pk):
        application = get_object_or_404(InternshipApplication, pk=pk)

        mentor = CompanyMentor.objects.filter(user=request.user).first()
        if not mentor:
            raise PermissionDenied("Only company mentors can review applications.")

        # Ensure mentor belongs to the company
        if application.position.company != mentor.company:
            raise PermissionDenied("Not your company")

        if application.dept_status != "APPROVED":
            raise ValidationError("Application not approved by department")

        if application.mentor_status not in [None, "PENDING"]:
            raise ValidationError("Already reviewed by mentor")

        action = request.data.get("action")

        if action == "accept":
            application.mentor_status = "ACCEPTED"
            application.mentor = mentor

        elif action == "reject":
            application.mentor_status = "REJECTED"

        else:
            raise ValidationError("Invalid action")

        application.save()

        return Response({"message": "Mentor decision recorded"}, status=200)
