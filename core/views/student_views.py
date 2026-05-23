from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Internship, InternshipApplication
from core.permissions import IsStudentUser


class AcceptOfferSerializer(serializers.Serializer):
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)


class AcceptOfferView(APIView):
    permission_classes = [IsAuthenticated, IsStudentUser]
    serializer_class = AcceptOfferSerializer

    def post(self, request, pk):
        application = get_object_or_404(
            InternshipApplication, pk=pk, student=request.user.student_profile
        )

        if application.dept_status != "APPROVED":
            raise ValidationError("Coordinator has not approved this application yet.")

        if application.mentor_status != "ACCEPTED":
            raise ValidationError(
                "Company mentor has not accepted this application yet."
            )

        if application.student_decision == "ACCEPTED":
            raise ValidationError("Already accepted")

        position = application.position
        accepted_count = InternshipApplication.objects.filter(
            position=position,
            student_decision="ACCEPTED",
        ).count()
        if (
            position.max_applicants is not None
            and accepted_count >= position.max_applicants
        ):
            raise ValidationError("Position is full")

        # Prevent multiple active or scheduled internships
        if Internship.objects.filter(
            student=application.student, status__in=["NOT_STARTED", "ONGOING"]
        ).exists():
            raise ValidationError("You already have an active internship")

        start_date_raw = request.data.get("start_date")
        end_date_raw = request.data.get("end_date")

        internship = Internship.objects.create(
            student=application.student,
            position=application.position,
            company=application.position.company,
            mentor=application.mentor,
            supervisor=application.supervisor,
            start_date=start_date_raw or None,
            end_date=end_date_raw or None,
            status="NOT_STARTED",
        )

        # Auto-decline all other offers
        InternshipApplication.objects.filter(
            student=application.student, mentor_status="ACCEPTED"
        ).exclude(id=application.id).update(student_decision="DECLINED")

        from core.services.application_service import process_student_confirmation

        try:
            process_student_confirmation(
                application=application,
                actor=request.user,
                decision="accept",
            )
        except ValueError as exc:
            raise ValidationError(str(exc))

        return Response(
            {"message": "Offer accepted", "internship_id": internship.id}, status=201
        )
