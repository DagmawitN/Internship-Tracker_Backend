from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status, generics, serializers
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.db import models
from django.utils import timezone
from core.models import (
    WeeklyLogbook,
    InternshipApplication,
    DailyLogEntry,
    Report,
    ReportFile,
    Student,
    AdvisorAssignment,
    FinalIndustryEvaluation,
    CompanyMentor
)
from core.serializers.report_serializers import (
    WeeklyLogbookSerializer,
    DailyLogEntrySerializer,
    SubmitFinalReportSerializer,
    AdvisorFinalReportListSerializer,
    AdvisorWeeklyLogbookSerializer,
    FinalIndustryEvaluationSerializer
)

class AddDailyLogEntryAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, logbook_id):

        try:
            logbook = WeeklyLogbook.objects.get(id=logbook_id)

        except WeeklyLogbook.DoesNotExist:
            return Response(
                {"error": "Logbook not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        if logbook.status != "DRAFT":
            return Response(
                {"error": "Cannot edit submitted logbook."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = DailyLogEntrySerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        serializer.save(
            weekly_logbook=logbook
        )

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )


class CreateWeeklyLogbookAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        if not hasattr(request.user, "student_profile"):
            return Response(
                {"error": "Only students can create logbooks."},
                status=status.HTTP_403_FORBIDDEN
            )

        week_number = request.data.get("week_number")

        if not week_number:
            return Response(
                {"error": "week_number is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        student = request.user.student_profile

        internship = InternshipApplication.objects.filter(
            student=student,
            status="ONGOING"
        ).first()

        if not internship:
            return Response(
                {"error": "No active internship found."},
                status=status.HTTP_404_NOT_FOUND
            )

        existing_logbook = WeeklyLogbook.objects.filter(
            internship=internship,
            week_number=week_number
        ).exists()

        if existing_logbook:
            return Response(
                {"error": "Weekly logbook already exists."},
                status=status.HTTP_400_BAD_REQUEST
            )

        logbook = WeeklyLogbook.objects.create(
            internship=internship,
            week_number=week_number
        )

        serializer = WeeklyLogbookSerializer(logbook)

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )


class SubmitFinalReportAPIView(APIView):
    """
    API endpoint for authenticated students to submit and download their final internship report.
    POST: Submit final report with file upload.
    GET: Download the submitted final report.
    """
    permission_classes = [IsAuthenticated]

    def _has_permission(self, user, student):
        """
        Check if user has permission to access the student's final report.
        """
        # Student can access their own report
        if hasattr(user, 'student_profile') and user.student_profile == student:
            return True
        
        # Advisors, coordinators, examiners can access assigned students
        if AdvisorAssignment.objects.filter(
            models.Q(coordinator=user) | models.Q(advisor=user),
            student=student
        ).exists():
            return True
        
        # Staff members in the same department can access
        if hasattr(user, 'staff') and user.staff.department == student.department:
            return True
        
        return False

    def post(self, request, student_id):
        # Check if user is a student
        if not hasattr(request.user, 'student_profile'):
            return Response(
                {"error": "Only students can submit final reports."},
                status=status.HTTP_403_FORBIDDEN
            )

        student = request.user.student_profile

        # Ensure student can only submit their own report
        if student.id != student_id:
            return Response(
                {"error": "Students can only submit their own reports."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Find student's active or completed internship
        internship = InternshipApplication.objects.filter(
            student=student,
            status__in=['ONGOING', 'COMPLETED']
        ).first()

        if not internship:
            return Response(
                {"error": "No active or completed internship found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if FINAL report already submitted
        if Report.objects.filter(
            internship=internship,
            report_type='FINAL'
        ).exists():
            return Response(
                {"error": "Final report already submitted for this internship."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate and create report
        serializer = SubmitFinalReportSerializer(data=request.data)
        if serializer.is_valid():
            report = serializer.save(
                internship=internship,
                report_type='FINAL',
                status='SUBMITTED',
                submission_date=timezone.now
            )
            return Response({
                "message": "Final report submitted successfully",
                "report_id": report.id,
                "status": "SUBMITTED"
            }, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request, student_id):
        """
        API endpoint for authenticated users to download a student's final internship report.
        """
        # Get the student
        student = get_object_or_404(Student, id=student_id)

        # Check permissions
        if not self._has_permission(request.user, student):
            return Response(
                {"error": "You do not have permission to view this report."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Find student's active or completed internship
        internship = InternshipApplication.objects.filter(
            student=student,
            status__in=['ONGOING', 'COMPLETED']
        ).first()

        if not internship:
            return Response(
                {"error": "No active or completed internship found for this student."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Find the FINAL report
        try:
            report = Report.objects.get(
                internship=internship,
                report_type='FINAL'
            )
        except Report.DoesNotExist:
            return Response(
                {"error": "Final report not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get the report file
        try:
            report_file = ReportFile.objects.get(report=report)
        except ReportFile.DoesNotExist:
            return Response(
                {"error": "Report file not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Return the file as download
        file_path = report_file.file.path
        response = FileResponse(
            open(file_path, 'rb'),
            as_attachment=True,
            filename=report_file.file_name
        )
        return response


class AdvisorFinalReportListAPIView(APIView):
    """
    API endpoint for advisors to view FINAL internship reports
    submitted by students assigned to them.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Check if user has Advisor role
        if not hasattr(request.user, 'role') or request.user.role.role_name != 'Advisor':
            return Response(
                {"error": "Only advisors can access this endpoint."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get internships assigned to this advisor
        assigned_internships = AdvisorAssignment.objects.filter(
            advisor=request.user
        ).values_list('internship', flat=True)

        # Get FINAL reports for those internships
        reports = Report.objects.filter(
            report_type='FINAL',
            internship__in=assigned_internships
        ).select_related(
            'internship__student__user',
            'internship__position__company'
        ).prefetch_related(
            'files'
        ).order_by('-submission_date')

        serializer = AdvisorFinalReportListSerializer(reports, many=True)
        return Response(serializer.data)


class AdvisorWeeklyLogbookListAPIView(APIView):
    """
    API endpoint for advisors to view weekly logbooks submitted by students
    assigned to them.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Check if user has Advisor role
        if not hasattr(request.user, 'role') or request.user.role.role_name != 'Advisor':
            return Response(
                {"error": "Only advisors can access this endpoint."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get internships assigned to this advisor
        assigned_internships = AdvisorAssignment.objects.filter(
            advisor=request.user
        ).values_list('internship', flat=True)

        # Get weekly logbooks for those internships, ordered by newest week first
        logbooks = WeeklyLogbook.objects.filter(
            internship__in=assigned_internships
        ).select_related(
            'internship__student__user',
            'internship__position__company'
        ).prefetch_related(
            'daily_entries'
        ).order_by('-week_number')

        serializer = AdvisorWeeklyLogbookSerializer(logbooks, many=True)
        return Response(serializer.data)


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

