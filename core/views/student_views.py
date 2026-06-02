from django.db import models
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Internship, InternshipApplication, SelfPlacementRequest
from core.permissions import IsCoordinatorUser, IsStudentUser
from core.serializers.self_placement_serializer import SelfPlacementRequestSerializer


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


class StudentCurrentPlacementView(APIView):
    permission_classes = [IsAuthenticated, IsStudentUser]

    def get(self, request):
        student = request.user.student_profile

        internship = (
            Internship.objects.filter(student=student)
            .select_related(
                "position",
                "position__company",
                "mentor__user",
                "supervisor__user",
            )
            .order_by("-id")
            .first()
        )

        application = (
            InternshipApplication.objects.filter(
                student=student,
                student_decision="ACCEPTED",
            )
            .select_related(
                "position",
                "position__company",
                "advisor__user",
                "mentor__user",
                "supervisor__user",
            )
            .order_by("-created_at")
            .first()
        )

        internship_id = internship.id if internship else None

        if not internship and not application:
            return Response({"placement": None}, status=200)

        if internship:
            # Get examiner assignments for the student's application
            from core.models import AdvisorAssignment
            app_for_examiners = (
                InternshipApplication.objects.filter(
                    student=student,
                    position=internship.position,
                )
                .filter(
                    models.Q(dept_status="APPROVED")
                    | models.Q(student_decision="ACCEPTED")
                    | models.Q(mentor_status="ACCEPTED")
                )
                .order_by("-created_at")
                .first()
            )
            examiner_names = []
            if app_for_examiners:
                examiner_assignments = (
                    AdvisorAssignment.objects.filter(
                        internship_id=app_for_examiners.id, role="EXAMINER"
                    ).select_related("advisor").order_by("id")
                )
                examiner_names = [
                    a.advisor.get_full_name() or a.advisor.username
                    for a in examiner_assignments
                ]

            return Response(
                {
                    "internship_id": internship_id,
                    "placement": {
                        "type": "internship",
                        "id": app_for_examiners.id if app_for_examiners else internship.id,
                        "application_id": app_for_examiners.id if app_for_examiners else None,
                        "status": internship.status,
                        "student_id": student.student_id,
                        "student_name": request.user.get_full_name().strip() or request.user.username,
                        "internship_id": internship.id,
                        "company_id": internship.company_id,
                        "company_name": internship.company.company_name if internship.company else internship.position.company.company_name,
                        "position_id": internship.position_id,
                        "position_title": internship.position.title if internship.position else None,
                        "start_date": internship.start_date,
                        "end_date": internship.end_date,
                        "total_hours": internship.total_hours,
                        "advisor_name": student.advisor.user.get_full_name().strip() if getattr(student, "advisor", None) and student.advisor.user else None,
                        "examiner_name": examiner_names[0] if len(examiner_names) > 0 else None,
                        "examiner2_name": examiner_names[1] if len(examiner_names) > 1 else None,
                        "mentor_name": internship.mentor.user.get_full_name().strip() if internship.mentor and internship.mentor.user else None,
                        "supervisor_name": internship.supervisor.user.get_full_name().strip() if internship.supervisor and internship.supervisor.user else None,
                        "dept_status": app_for_examiners.dept_status if app_for_examiners else "APPROVED",
                        "mentor_status": app_for_examiners.mentor_status if app_for_examiners else "ACCEPTED",
                        "student_decision": app_for_examiners.student_decision if app_for_examiners else "ACCEPTED",
                        "applied_at": app_for_examiners.created_at if app_for_examiners else internship.created_at,
                    }
                },
                status=200,
            )

        workflow_status = application.overall_status
        # Get examiner assignments
        from core.models import AdvisorAssignment
        examiner_assignments = (
            AdvisorAssignment.objects.filter(
                internship_id=application.id, role="EXAMINER"
            ).select_related("advisor").order_by("id")
        )
        examiner_names = [
            a.advisor.get_full_name() or a.advisor.username
            for a in examiner_assignments
        ]
        return Response(
            {
                "internship_id": internship_id,
                "placement": {
                    "type": "application",
                    "id": application.id,
                    "application_id": application.id,
                    "status": workflow_status,
                    "student_id": student.student_id,
                    "student_name": request.user.get_full_name().strip() or request.user.username,
                    "internship_id": None,
                    "company_id": application.position.company_id if application.position else None,
                    "company_name": application.position.company.company_name if application.position and application.position.company else None,
                    "position_id": application.position_id,
                    "position_title": application.position.title if application.position else None,
                    "start_date": application.requested_start_date,
                    "end_date": application.requested_end_date,
                    "total_hours": None,
                    "advisor_name": application.advisor.user.get_full_name().strip() if application.advisor and application.advisor.user else (
                        student.advisor.user.get_full_name().strip() if getattr(student, "advisor", None) and student.advisor.user else None
                    ),
                    "examiner_name": examiner_names[0] if len(examiner_names) > 0 else None,
                    "examiner2_name": examiner_names[1] if len(examiner_names) > 1 else None,
                    "mentor_name": application.mentor.user.get_full_name().strip() if application.mentor and application.mentor.user else None,
                    "supervisor_name": application.supervisor.user.get_full_name().strip() if application.supervisor and application.supervisor.user else None,
                    "overall_status": workflow_status,
                    "dept_status": application.dept_status,
                    "mentor_status": application.mentor_status,
                    "student_decision": application.student_decision,
                }
            },
            status=200,
        )


class SelfPlacementRequestView(APIView):
    permission_classes = [IsAuthenticated, IsStudentUser]
    serializer_class = SelfPlacementRequestSerializer

    def get(self, request):
        request_obj = (
            SelfPlacementRequest.objects.filter(student=request.user.student_profile)
            .order_by("-created_at")
            .first()
        )
        if not request_obj:
            return Response({"request": None}, status=200)

        return Response({"request": self.serializer_class(request_obj).data}, status=200)

    def post(self, request):
        student = request.user.student_profile
        existing = SelfPlacementRequest.objects.filter(
            student=student,
            status__in=[SelfPlacementRequest.Status.PENDING, SelfPlacementRequest.Status.APPROVED],
        ).first()
        if existing:
            return Response(
                {
                    "request": self.serializer_class(existing).data,
                    "detail": "You already have a self-placement request awaiting review.",
                },
                status=200,
            )

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        self_placement_request = serializer.save(student=student)
        return Response(
            {"request": self.serializer_class(self_placement_request).data},
            status=201,
        )


class SelfPlacementRequestReviewView(APIView):
    permission_classes = [IsAuthenticated, IsCoordinatorUser]

    def patch(self, request, pk):
        request_obj = get_object_or_404(SelfPlacementRequest, pk=pk)
        action = str(request.data.get("action", "")).strip().lower()
        review_notes = str(request.data.get("review_notes", "")).strip()

        if action not in {"approve", "reject"}:
            raise ValidationError({'action': 'Action must be "approve" or "reject".'})

        request_obj.status = (
            SelfPlacementRequest.Status.APPROVED
            if action == "approve"
            else SelfPlacementRequest.Status.REJECTED
        )
        request_obj.review_notes = review_notes
        request_obj.reviewed_by = request.user
        request_obj.reviewed_at = timezone.now()
        request_obj.save(update_fields=["status", "review_notes", "reviewed_by", "reviewed_at"])

        return Response(
            {"request": SelfPlacementRequestSerializer(request_obj).data},
            status=200,
        )
