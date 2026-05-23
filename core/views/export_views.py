"""
Export views — users export their own data as CSV.

Scoping rules:
  Student   — only own data
  Advisor   — assigned students' data only
  Coordinator — department students' data only
"""

import csv
import io

from django.http import HttpResponse
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.models import (
    AdvisorEvaluation,
    Attendance,
    CompanyMentor,
    FinalIndustryEvaluation,
    Internship,
    InternshipApplication,
    Report,
    Student,
)


def _get_role(user):
    return getattr(user.role, "role_name", None) if user.role else None


def _csv_response(filename: str) -> tuple[HttpResponse, csv.writer]:
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    return response, writer


# ---------------------------------------------------------------------------
# Internship export
# ---------------------------------------------------------------------------


class ExportMyInternshipsView(APIView):
    """GET /exports/my/internships/"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        role = _get_role(user)

        base_qs = Internship.objects.select_related(
            "student__user",
            "student__department",
            "student__advisor__user",
            "position",
            "position__company",
            "company",
        )

        if role == "STUDENT":
            qs = base_qs.filter(student__user=user)
        elif role == "ADVISOR":
            qs = base_qs.filter(student__advisor__user=user)
        elif role == "COORDINATOR":
            staff = getattr(user, "staff", None)
            if not staff:
                return HttpResponse("Coordinator profile not found.", status=403)
            qs = base_qs.filter(student__department=staff.department)
        elif role == "ADMIN":
            qs = base_qs.all()
        else:
            return HttpResponse("Not authorized.", status=403)

        response, writer = _csv_response(
            f"internships_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        writer.writerow(
            [
                "ID",
                "Student Name",
                "Student Email",
                "Student ID",
                "Department",
                "Position Title",
                "Company",
                "Work Mode",
                "Status",
                "Start Date",
                "End Date",
                "Total Hours",
                "Advisor",
            ]
        )
        for obj in qs:
            advisor = obj.student.advisor
            advisor_name = (
                (advisor.user.get_full_name() or advisor.user.username)
                if advisor
                else ""
            )
            writer.writerow(
                [
                    obj.id,
                    obj.student.user.get_full_name() or obj.student.user.username,
                    obj.student.user.email,
                    obj.student.student_id,
                    obj.student.department.department_name,
                    obj.position.title,
                    (
                        obj.company.company_name
                        if obj.company
                        else obj.position.company.company_name
                    ),
                    getattr(obj.position, "work_mode", ""),
                    obj.status,
                    obj.start_date or "",
                    obj.end_date or "",
                    obj.total_hours,
                    advisor_name,
                ]
            )
        return response


# ---------------------------------------------------------------------------
# Reports export
# ---------------------------------------------------------------------------


class ExportMyReportsView(APIView):
    """GET /exports/my/reports/"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        role = _get_role(user)

        base_qs = Report.objects.select_related(
            "internship__student__user",
            "internship__position__company",
        )

        if role == "STUDENT":
            qs = base_qs.filter(internship__student__user=user)
        elif role == "ADVISOR":
            qs = base_qs.filter(internship__student__advisor__user=user)
        elif role == "COORDINATOR":
            staff = getattr(user, "staff", None)
            if not staff:
                return HttpResponse("Coordinator profile not found.", status=403)
            qs = base_qs.filter(internship__student__department=staff.department)
        elif role == "ADMIN":
            qs = base_qs.all()
        else:
            return HttpResponse("Not authorized.", status=403)

        response, writer = _csv_response(
            f"reports_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        writer.writerow(
            [
                "Report ID",
                "Student Name",
                "Student Email",
                "Report Type",
                "Title",
                "Status",
                "Submission Date",
                "Company",
            ]
        )
        for obj in qs:
            student = obj.internship.student
            writer.writerow(
                [
                    obj.id,
                    student.user.get_full_name() or student.user.username,
                    student.user.email,
                    obj.report_type,
                    obj.title,
                    obj.status,
                    obj.submission_date or "",
                    obj.internship.position.company.company_name,
                ]
            )
        return response


# ---------------------------------------------------------------------------
# Evaluations export
# ---------------------------------------------------------------------------


class ExportMyEvaluationsView(APIView):
    """GET /exports/my/evaluations/"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        role = _get_role(user)

        adv_qs = AdvisorEvaluation.objects.select_related(
            "internship__student__user",
            "internship__position__company",
            "advisor",
        )
        ind_qs = FinalIndustryEvaluation.objects.select_related(
            "internship__student__user",
            "internship__position__company",
            "company_mentor__user",
        )

        if role == "STUDENT":
            adv_qs = adv_qs.filter(internship__student__user=user)
            ind_qs = ind_qs.filter(internship__student__user=user)
        elif role == "ADVISOR":
            adv_qs = adv_qs.filter(internship__student__advisor__user=user)
            ind_qs = ind_qs.filter(internship__student__advisor__user=user)
        elif role == "COORDINATOR":
            staff = getattr(user, "staff", None)
            if not staff:
                return HttpResponse("Coordinator profile not found.", status=403)
            adv_qs = adv_qs.filter(internship__student__department=staff.department)
            ind_qs = ind_qs.filter(internship__student__department=staff.department)
        elif role == "ADMIN":
            pass  # full access
        else:
            return HttpResponse("Not authorized.", status=403)

        response, writer = _csv_response(
            f"evaluations_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        writer.writerow(
            [
                "Type",
                "Student Name",
                "Student Email",
                "Company",
                "Total Score",
                "Weighted / Overall Score",
                "Submitted At",
                "Evaluator",
            ]
        )
        for obj in adv_qs:
            student = obj.internship.student
            writer.writerow(
                [
                    "Advisor Evaluation",
                    student.user.get_full_name() or student.user.username,
                    student.user.email,
                    obj.internship.position.company.company_name,
                    obj.total_score,
                    obj.weighted_score,
                    obj.submitted_at or "",
                    obj.advisor.get_full_name() if obj.advisor else "",
                ]
            )
        for obj in ind_qs:
            student = obj.internship.student
            writer.writerow(
                [
                    "Industry Evaluation",
                    student.user.get_full_name() or student.user.username,
                    student.user.email,
                    obj.internship.position.company.company_name,
                    obj.total_mark,
                    obj.overall_student_performance,
                    obj.submitted_at or "",
                    (
                        obj.company_mentor.user.get_full_name()
                        if obj.company_mentor
                        else ""
                    ),
                ]
            )
        return response


# ---------------------------------------------------------------------------
# Attendance export
# ---------------------------------------------------------------------------


class ExportMyAttendanceView(APIView):
    """GET /exports/my/attendance/"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        role = _get_role(user)

        base_qs = Attendance.objects.select_related(
            "internship__student__user",
            "internship__student__department",
            "internship__position",
            "internship__company",
        )

        if role == "STUDENT":
            qs = base_qs.filter(internship__student__user=user)
        elif role == "ADVISOR":
            qs = base_qs.filter(internship__student__advisor__user=user)
        elif role == "COORDINATOR":
            staff = getattr(user, "staff", None)
            if not staff:
                return HttpResponse("Coordinator profile not found.", status=403)
            qs = base_qs.filter(internship__student__department=staff.department)
        elif role == "ADMIN":
            qs = base_qs.all()
        else:
            return HttpResponse("Not authorized.", status=403)

        response, writer = _csv_response(
            f"attendance_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        writer.writerow(
            [
                "Attendance ID",
                "Student Name",
                "Student Email",
                "Department",
                "Position Title",
                "Company",
                "Work Mode",
                "Date",
                "Check-In Time",
                "Check-Out Time",
                "Total Hours",
                "Status",
                "Location Verified",
                "Latitude",
                "Longitude",
            ]
        )
        for obj in qs:
            student = obj.internship.student
            company = obj.internship.company or obj.internship.position.company
            writer.writerow(
                [
                    obj.id,
                    student.user.get_full_name() or student.user.username,
                    student.user.email,
                    student.department.department_name,
                    obj.internship.position.title,
                    company.company_name if company else "",
                    getattr(obj.internship.position, "work_mode", ""),
                    obj.date,
                    obj.check_in_time or "",
                    obj.check_out_time or "",
                    obj.total_hours or "",
                    obj.status,
                    obj.is_location_verified,
                    obj.latitude or "",
                    obj.longitude or "",
                ]
            )
        return response
