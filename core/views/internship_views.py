from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from core.models import InternshipApplication, InternshipPosition, Company,CompanyMentor
from core.serializers.internship_serializer import InternshipApplicationSerializer,InternshipPositionSerializer
from core.permissions import IsStudentUser,IsCompanyMentor,IsMentorOfCompany

class InternshipApplicationCreateView(generics.CreateAPIView):
    serializer_class = InternshipApplicationSerializer
    permission_classes = [IsAuthenticated,IsStudentUser]

    def get_queryset(self):
        return InternshipApplication.objects.filter(student=self.request.user)
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['position_id'] = self.kwargs['pk']
        return context

class InternshipListCreateView(generics.ListCreateAPIView):
    serializer_class = InternshipPositionSerializer
    permission_classes = [IsAuthenticated]
    queryset = InternshipPosition.objects.all()

    def get_queryset(self):
        return InternshipPosition.objects.filter(is_active=True)

    def perform_create(self, serializer):
        if not CompanyMentor.objects.filter(user=self.request.user).exists():
            raise PermissionDenied("Only company mentors can create internships")

        mentor = CompanyMentor.objects.get(user=self.request.user)
        serializer.save(company=mentor.company)


class InternshipRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    serializer_class = InternshipPositionSerializer
    permission_classes = [IsAuthenticated, IsCompanyMentor, IsMentorOfCompany]
    queryset = InternshipPosition.objects.all()

    def perform_update(self, serializer):
        mentor = CompanyMentor.objects.get(user=self.request.user)

        if serializer.instance.company != mentor.company:
            raise PermissionDenied(
                "You cannot update internships from another company"
            )

        serializer.save()