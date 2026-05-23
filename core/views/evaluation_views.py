from rest_framework import generics, serializers
from rest_framework.permissions import IsAuthenticated

from core.models import (
    AdvisorAssignment,
    AdvisorEvaluation,
    CompanyMentor,
    FinalIndustryEvaluation,
)
from core.serializers.evaluation_serializers import (
    AdvisorEvaluationSerializer,
    FinalIndustryEvaluationSerializer,
)


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
        company_mentor_ids = CompanyMentor.objects.filter(user=user).values_list(
            "pk", flat=True
        )
        if company_mentor_ids:
            return FinalIndustryEvaluation.objects.filter(
                company_mentor__in=company_mentor_ids
            ).select_related(
                "internship__student__user",
                "internship__position__company",
                "company_mentor__user",
            )

        # Check if user is an advisor
        if hasattr(user, "role") and user.role.role_name == "Advisor":
            assigned_internships = AdvisorAssignment.objects.filter(
                advisor=user
            ).values_list("internship", flat=True)

            return FinalIndustryEvaluation.objects.filter(
                internship__in=assigned_internships
            ).select_related(
                "internship__student__user",
                "internship__position__company",
                "company_mentor__user",
            )

        # Default: no access
        return FinalIndustryEvaluation.objects.none()

    def perform_create(self, serializer):
        """
        Ensure only company mentors can create evaluations and validate permissions.
        """
        # Get internship
        internship = serializer.validated_data.get("internship")
        if internship is None:
            raise serializers.ValidationError("Internship must be provided.")

        company_mentor = CompanyMentor.objects.filter(
            user=self.request.user,
            id=internship.mentor_id,
        ).first()
        if company_mentor is None:
            raise serializers.ValidationError(
                "Only the company mentor assigned to this internship can submit the evaluation."
            )

        # Check if evaluation already exists
        if FinalIndustryEvaluation.objects.filter(internship=internship).exists():
            raise serializers.ValidationError(
                "Final evaluation for this internship already exists."
            )

        # Save with company mentor
        serializer.save(company_mentor=company_mentor)

        from core.services.audit_service import log_audit_event

        evaluation = serializer.instance
        log_audit_event(
            actor=self.request.user,
            action="EVALUATION_CREATED",
            target_type="FinalIndustryEvaluation",
            target_id=evaluation.id,
            description=f"Final industry evaluation created for internship {internship.id}.",
        )


class FinalIndustryEvaluationDetailAPIView(generics.RetrieveAPIView):
    """
    API endpoint to retrieve a specific final industry evaluation.
    GET: Retrieve evaluation details
    """

    permission_classes = [IsAuthenticated]
    serializer_class = FinalIndustryEvaluationSerializer
    lookup_field = "id"

    def get_queryset(self):
        """Filter evaluations for authorized users."""
        user = self.request.user

        # Check if user is a company mentor
        company_mentor_ids = CompanyMentor.objects.filter(user=user).values_list(
            "pk", flat=True
        )
        if company_mentor_ids:
            return FinalIndustryEvaluation.objects.filter(
                company_mentor__in=company_mentor_ids
            ).select_related(
                "internship__student__user",
                "internship__position__company",
                "company_mentor__user",
            )

        # Check if user is an advisor
        if hasattr(user, "role") and user.role.role_name == "Advisor":
            assigned_internships = AdvisorAssignment.objects.filter(
                advisor=user
            ).values_list("internship", flat=True)

            return FinalIndustryEvaluation.objects.filter(
                internship__in=assigned_internships
            ).select_related(
                "internship__student__user",
                "internship__position__company",
                "company_mentor__user",
            )

        return FinalIndustryEvaluation.objects.none()


class AdvisorEvaluationListCreateAPIView(generics.ListCreateAPIView):
    """
    API endpoint for advisors to submit and view advisor evaluations.
    POST: Create a new advisor evaluation
    GET: List advisor evaluations
    """

    permission_classes = [IsAuthenticated]
    serializer_class = AdvisorEvaluationSerializer

    def get_queryset(self):
        """
        Filter evaluations based on user role:
        - Advisors see evaluations they submitted
        - Other authorized users can view
        """
        user = self.request.user

        # Advisors see their own evaluations
        return AdvisorEvaluation.objects.filter(advisor=user).select_related(
            "internship__student__user", "internship__position__company", "advisor"
        )

    def perform_create(self, serializer):
        """
        Ensure only assigned advisors can create evaluations.
        """
        # Get internship
        internship = serializer.validated_data.get("internship")
        if internship is None:
            raise serializers.ValidationError("Internship must be provided.")

        # Verify advisor is assigned to this internship
        is_assigned = AdvisorAssignment.objects.filter(
            internship=internship,
            advisor=self.request.user,
        ).exists()

        if not is_assigned:
            raise serializers.ValidationError(
                "Only the advisor assigned to this internship can submit the evaluation."
            )

        # Check if evaluation already exists
        if AdvisorEvaluation.objects.filter(internship=internship).exists():
            raise serializers.ValidationError(
                "Advisor evaluation for this internship already exists."
            )

        # Save with advisor
        serializer.save(advisor=self.request.user)

        from core.services.audit_service import log_audit_event

        evaluation = serializer.instance
        log_audit_event(
            actor=self.request.user,
            action="EVALUATION_CREATED",
            target_type="AdvisorEvaluation",
            target_id=evaluation.id,
            description=f"Advisor evaluation created for internship {internship.id}.",
        )


class AdvisorEvaluationDetailAPIView(generics.RetrieveAPIView):
    """
    API endpoint to retrieve a specific advisor evaluation.
    GET: Retrieve evaluation details
    """

    permission_classes = [IsAuthenticated]
    serializer_class = AdvisorEvaluationSerializer
    lookup_field = "id"

    def get_queryset(self):
        """Filter evaluations for authorized advisors."""
        user = self.request.user

        # Return evaluations submitted by the current advisor
        return AdvisorEvaluation.objects.filter(advisor=user).select_related(
            "internship__student__user", "internship__position__company", "advisor"
        )
