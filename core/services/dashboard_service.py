"""
Dashboard service layer.

Each function returns a plain dict ready for DRF Response.
Views should call these functions and do nothing else.
"""

import datetime
import logging

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone

from core.models import (
    Advisor,
    AdvisorEvaluation,
    Attendance,
    Company,
    CompanyMentor,
    Department,
    FinalIndustryEvaluation,
    Internship,
    InternshipApplication,
    InternshipPosition,
    Notification,
    Report,
    Student,
    UserRole,
    WeeklyLogbook,
)

logger = logging.getLogger(__name__)

User = get_user_model()

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _calculate_attendance_rate(internship) -> float:
    """
    Return attendance rate (0–100) for a single Internship instance.
    Uses the position's working_days schedule.  Falls back to Mon–Fri
    when no schedule is defined.
    """
    if not internship.start_date:
        return 0.0

    working_days = [d.upper() for d in (internship.position.working_days or [])]
    if not working_days:
        working_days = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"]

    today = timezone.localdate()
    end = min(internship.end_date or today, today)
    start = internship.start_date

    if end < start:
        return 0.0

    # Count expected working days in the period
    expected = 0
    current = start
    while current <= end:
        if current.strftime("%A").upper() in working_days:
            expected += 1
        current += datetime.timedelta(days=1)

    if expected == 0:
        return 0.0

    attended = Attendance.objects.filter(
        internship=internship,
        status__in=["PRESENT", "LATE"],
    ).count()

    return round((attended / expected) * 100, 1)


def _safe_float(value, default=0.0):
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Student dashboard
# ---------------------------------------------------------------------------


def get_student_dashboard(user: "User") -> dict:
    """Return dashboard data for a single student."""
    try:
        student = user.student_profile
    except Exception:
        logger.warning("get_student_dashboard: user %s has no student_profile", user)
        return {}

    # Active internship
    internship = (
        Internship.objects.filter(student=student, status="ONGOING")
        .select_related("position__company", "position", "mentor__user")
        .first()
    )

    # Linked application (for reports / evaluations)
    application = (
        InternshipApplication.objects.filter(
            student=student,
            student_decision="ACCEPTED",
        )
        .select_related("position__company")
        .first()
    )

    # --- Attendance summary ---
    attendance_summary = {}
    if internship:
        agg = Attendance.objects.filter(internship=internship).aggregate(
            total=Count("id"),
            present=Count("id", filter=Q(status="PRESENT")),
            late=Count("id", filter=Q(status="LATE")),
            absent=Count("id", filter=Q(status="ABSENT")),
            hours=Sum("total_hours"),
        )
        attendance_summary = {
            "total_days": agg["total"],
            "present_days": agg["present"],
            "late_days": agg["late"],
            "absent_days": agg["absent"],
            "total_hours": _safe_float(agg["hours"]),
            "attendance_rate": _calculate_attendance_rate(internship),
        }

    # --- Reports summary ---
    reports_summary = {}
    if application:
        ragg = Report.objects.filter(internship=application).aggregate(
            total=Count("id"),
            submitted=Count("id", filter=Q(status="SUBMITTED")),
            reviewed=Count("id", filter=Q(status="REVIEWED")),
        )
        reports_summary = {
            "total": ragg["total"],
            "submitted": ragg["submitted"],
            "reviewed": ragg["reviewed"],
            "pending_review": ragg["submitted"],
        }

    # --- Evaluations summary ---
    evaluations_summary = {}
    if application:
        adv_eval = AdvisorEvaluation.objects.filter(internship=application).first()
        ind_eval = FinalIndustryEvaluation.objects.filter(
            internship=application
        ).first()
        evaluations_summary = {
            "advisor_evaluation": {
                "completed": adv_eval is not None,
                "weighted_score": _safe_float(adv_eval.weighted_score)
                if adv_eval
                else None,
            },
            "industry_evaluation": {
                "completed": ind_eval is not None,
                "overall_performance": _safe_float(ind_eval.overall_student_performance)
                if ind_eval
                else None,
            },
        }

    # --- Advisor info ---
    advisor_info = None
    if student.advisor:
        adv = student.advisor
        advisor_info = {
            "id": adv.id,
            "name": adv.user.get_full_name() or adv.user.username,
            "email": adv.user.email,
            "department": adv.department.department_name,
        }

    # --- Active internship data ---
    active_internship_data = None
    if internship:
        active_internship_data = {
            "id": internship.id,
            "position_title": internship.position.title,
            "company": internship.position.company.company_name,
            "status": internship.status,
            "start_date": internship.start_date,
            "end_date": internship.end_date,
            "total_hours": _safe_float(internship.total_hours),
        }

    # --- My applications ---
    my_applications = []
    for app in (
        InternshipApplication.objects.filter(student=student)
        .select_related("position__company")
        .order_by("-created_at")
    ):
        my_applications.append(
            {
                "id": app.id,
                "position_title": app.position.title,
                "company_name": app.position.company.company_name,
                "overall_status": app.overall_status,
                "applied_at": app.created_at,
            }
        )

    # --- Recent notifications ---
    notifications = list(
        Notification.objects.filter(recipient=user)
        .order_by("-created_at")[:10]
        .values(
            "id",
            "title",
            "message",
            "notification_type",
            "is_read",
            "created_at",
        )
    )

    # --- Applications awaiting student confirmation ---
    awaiting_confirmation = []
    for app in (
        InternshipApplication.objects.filter(
            student=student,
            dept_status="APPROVED",
            mentor_status="ACCEPTED",
            student_decision="PENDING",
        )
        .select_related("position__company")
        .order_by("-created_at")
    ):
        awaiting_confirmation.append(
            {
                "id": app.id,
                "position_title": app.position.title,
                "company_name": app.position.company.company_name,
                "mentor_signed_at": app.mentor_signed_at,
                "applied_at": app.created_at,
            }
        )

    # --- Resume status ---
    resume_status = {
        "has_resume": bool(student.resume),
        "uploaded_at": student.resume_uploaded_at,
    }

    return {
        "active_internship": active_internship_data,
        "attendance_summary": attendance_summary,
        "reports_summary": reports_summary,
        "evaluations_summary": evaluations_summary,
        "advisor": advisor_info,
        "recent_notifications": notifications,
        "my_applications": my_applications,
        "applications_awaiting_confirmation": awaiting_confirmation,
        "resume_status": resume_status,
    }


# ---------------------------------------------------------------------------
# Advisor dashboard
# ---------------------------------------------------------------------------


def get_advisor_dashboard(user: "User") -> dict:
    """Return dashboard data for an advisor."""
    try:
        advisor = user.advisor_profile
    except Exception:
        logger.warning("get_advisor_dashboard: user %s has no advisor_profile", user)
        return {}

    student_ids = list(
        Student.objects.filter(advisor=advisor).values_list("id", flat=True)
    )
    student_count = len(student_ids)

    # Active internships for assigned students
    active_internships_qs = Internship.objects.filter(
        student__in=student_ids, status="ONGOING"
    ).select_related("student__user", "position")
    active_count = active_internships_qs.count()

    # Applications for assigned students
    app_ids = list(
        InternshipApplication.objects.filter(
            student__in=student_ids, student_decision="ACCEPTED"
        ).values_list("id", flat=True)
    )

    # Pending reports (submitted, not yet reviewed)
    pending_reports_count = Report.objects.filter(
        internship__in=app_ids, status="SUBMITTED"
    ).count()

    # Recently submitted reports (last 5)
    recent_reports = list(
        Report.objects.filter(internship__in=app_ids, status="SUBMITTED")
        .select_related("internship__student__user", "internship__position")
        .order_by("-submission_date")[:5]
        .values(
            "id",
            "report_type",
            "submission_date",
            "internship__student__user__email",
            "internship__position__title",
        )
    )

    # Attendance flags (students with <70 % attendance)
    attendance_flags = []
    for intern in active_internships_qs.select_related("position")[:30]:
        rate = _calculate_attendance_rate(intern)
        if rate < 70:
            attendance_flags.append(
                {
                    "internship_id": intern.id,
                    "student": intern.student.user.get_full_name()
                    or intern.student.user.username,
                    "student_email": intern.student.user.email,
                    "attendance_rate": rate,
                    "position": intern.position.title,
                }
            )

    # --- Applied students list ---
    applied_students = []
    for app in (
        InternshipApplication.objects.filter(student__in=student_ids)
        .select_related("student__user", "position__company")
        .order_by("-created_at")
    ):
        applied_students.append(
            {
                "student_id": app.student.id,
                "student_name": app.student.user.get_full_name()
                or app.student.user.username,
                "student_email": app.student.user.email,
                "overall_status": app.overall_status,
                "position_title": app.position.title,
                "company_name": app.position.company.company_name,
                "applied_at": app.created_at,
            }
        )

    # --- Student internship status breakdown ---
    status_counts = Internship.objects.filter(student__in=student_ids).aggregate(
        ONGOING=Count("id", filter=Q(status="ONGOING")),
        COMPLETED=Count("id", filter=Q(status="COMPLETED")),
        CANCELLED=Count("id", filter=Q(status="CANCELLED")),
        NOT_STARTED=Count("id", filter=Q(status="NOT_STARTED")),
    )
    student_statuses = {
        "ONGOING": status_counts["ONGOING"],
        "COMPLETED": status_counts["COMPLETED"],
        "CANCELLED": status_counts["CANCELLED"],
        "NOT_STARTED": status_counts["NOT_STARTED"],
    }

    # --- Pending review applications ---
    # mentor accepted the offer but advisor has not yet reviewed
    pending_review_applications = []
    for app in (
        InternshipApplication.objects.filter(
            student__in=student_ids,
            mentor_status="ACCEPTED",
            advisor_status="PENDING",
        )
        .select_related("student__user", "position__company")
        .order_by("-created_at")
    ):
        pending_review_applications.append(
            {
                "application_id": app.id,
                "student_name": app.student.user.get_full_name()
                or app.student.user.username,
                "position_title": app.position.title,
                "company_name": app.position.company.company_name,
                "mentor_status": app.mentor_status,
                "applied_at": app.created_at,
            }
        )

    # --- Active interns (ONGOING internships for assigned students) ---
    active_interns = []
    for intern in Internship.objects.filter(
        student__in=student_ids, status="ONGOING"
    ).select_related("student__user", "position__company", "position"):
        active_interns.append(
            {
                "internship_id": intern.id,
                "student_name": intern.student.user.get_full_name()
                or intern.student.user.username,
                "position_title": intern.position.title,
                "company_name": intern.position.company.company_name,
                "work_mode": getattr(intern.position, "work_mode", None),
                "start_date": intern.start_date,
                "attendance_rate": _calculate_attendance_rate(intern),
            }
        )

    return {
        "assigned_students": student_count,
        "active_internships": active_count,
        "pending_reports": pending_reports_count,
        "recent_reports": recent_reports,
        "attendance_flags": attendance_flags,
        "applied_students": applied_students,
        "student_statuses": student_statuses,
        "pending_review_applications": pending_review_applications,
        "active_interns": active_interns,
    }


# ---------------------------------------------------------------------------
# Mentor dashboard
# ---------------------------------------------------------------------------


def get_mentor_dashboard(user: "User") -> dict:
    """Return dashboard data for a company mentor."""
    mentor = CompanyMentor.objects.filter(user=user).select_related("company").first()
    if not mentor:
        return {}

    company = mentor.company

    internships_qs = Internship.objects.filter(company=company).select_related(
        "student__user", "position"
    )

    counts = internships_qs.aggregate(
        total=Count("id"),
        ongoing=Count("id", filter=Q(status="ONGOING")),
        completed=Count("id", filter=Q(status="COMPLETED")),
        not_started=Count("id", filter=Q(status="NOT_STARTED")),
        cancelled=Count("id", filter=Q(status="CANCELLED")),
    )

    # Pending applications (dept approved, mentor not reviewed yet)
    pending_applications = InternshipApplication.objects.filter(
        position__company=company,
        dept_status="APPROVED",
        mentor_status__isnull=True,
    ).count()

    # Attendance overview across all ongoing internships
    ongoing_ids = list(
        internships_qs.filter(status="ONGOING").values_list("id", flat=True)
    )
    att_overview = Attendance.objects.filter(internship__in=ongoing_ids).aggregate(
        total=Count("id"),
        present=Count("id", filter=Q(status="PRESENT")),
        late=Count("id", filter=Q(status="LATE")),
        absent=Count("id", filter=Q(status="ABSENT")),
    )

    # Per-intern progress (capped at 10 to avoid N+1 in large companies)
    intern_summaries = []
    for intern in internships_qs.filter(status="ONGOING")[:10]:
        agg = Attendance.objects.filter(internship=intern).aggregate(
            total=Count("id"),
            present=Count("id", filter=Q(status__in=["PRESENT", "LATE"])),
            hours=Sum("total_hours"),
        )
        intern_summaries.append(
            {
                "internship_id": intern.id,
                "student": intern.student.user.get_full_name()
                or intern.student.user.username,
                "position": intern.position.title,
                "start_date": intern.start_date,
                "attendance_days": agg["total"],
                "total_hours": _safe_float(agg["hours"]),
                "attendance_rate": _calculate_attendance_rate(intern),
            }
        )

    return {
        "company": company.company_name,
        "total_interns": counts["total"],
        "ongoing_internships": counts["ongoing"],
        "completed_internships": counts["completed"],
        "not_started_internships": counts["not_started"],
        "cancelled_internships": counts["cancelled"],
        "pending_applications": pending_applications,
        "attendance_overview": att_overview,
        "intern_summaries": intern_summaries,
    }


# ---------------------------------------------------------------------------
# Coordinator dashboard
# ---------------------------------------------------------------------------


def get_coordinator_dashboard(user: "User") -> dict:
    """Return dashboard data for a department coordinator."""
    staff = getattr(user, "staff", None)
    if not staff:
        return {}

    department = staff.department

    students_qs = Student.objects.filter(department=department).select_related("user")
    student_count = students_qs.count()
    student_ids = list(students_qs.values_list("id", flat=True))

    advisors_qs = Advisor.objects.filter(department=department).select_related("user")
    advisor_count = advisors_qs.count()

    # Internship counts for department students
    internships_qs = Internship.objects.filter(student__in=student_ids)
    int_counts = internships_qs.aggregate(
        total=Count("id"),
        ongoing=Count("id", filter=Q(status="ONGOING")),
        completed=Count("id", filter=Q(status="COMPLETED")),
        cancelled=Count("id", filter=Q(status="CANCELLED")),
        not_started=Count("id", filter=Q(status="NOT_STARTED")),
    )

    placed = (int_counts["total"] or 0) - (int_counts["cancelled"] or 0)
    placement_rate = round((placed / student_count) * 100, 1) if student_count else 0.0

    # Advisor workload
    advisor_workload = list(
        advisors_qs.annotate(student_count=Count("assigned_students")).values(
            "id",
            "user__email",
            "user__first_name",
            "user__last_name",
            "student_count",
        )
    )

    # Pending reports
    app_ids = list(
        InternshipApplication.objects.filter(
            student__in=student_ids, student_decision="ACCEPTED"
        ).values_list("id", flat=True)
    )
    pending_reports = Report.objects.filter(
        internship__in=app_ids, status="SUBMITTED"
    ).count()

    # Attendance flags for ongoing internships in department
    attendance_flags = []
    for intern in Internship.objects.filter(
        student__in=student_ids, status="ONGOING"
    ).select_related("student__user", "position")[:20]:
        rate = _calculate_attendance_rate(intern)
        if rate < 70:
            attendance_flags.append(
                {
                    "student": intern.student.user.email,
                    "attendance_rate": rate,
                    "position": intern.position.title,
                }
            )

    # --- Applied students list (up to 50 most recent) ---
    coord_applied_students = []
    for app in (
        InternshipApplication.objects.filter(student__in=student_ids)
        .select_related("student__user", "position__company")
        .order_by("-created_at")[:50]
    ):
        coord_applied_students.append(
            {
                "student_id": app.student.id,
                "student_name": app.student.user.get_full_name()
                or app.student.user.username,
                "overall_status": app.overall_status,
                "position_title": app.position.title,
                "company_name": app.position.company.company_name,
                "applied_at": app.created_at,
            }
        )

    # --- Active interns (up to 50) ---
    coord_active_interns = []
    for intern in Internship.objects.filter(
        student__in=student_ids, status="ONGOING"
    ).select_related(
        "student__user",
        "student__advisor__user",
        "position__company",
        "position",
    )[:50]:
        adv = getattr(intern.student, "advisor", None)
        advisor_name = adv.user.get_full_name() or adv.user.username if adv else None
        coord_active_interns.append(
            {
                "internship_id": intern.id,
                "student_name": intern.student.user.get_full_name()
                or intern.student.user.username,
                "position_title": intern.position.title,
                "company_name": intern.position.company.company_name,
                "work_mode": getattr(intern.position, "work_mode", None),
                "start_date": intern.start_date,
                "advisor_name": advisor_name,
            }
        )

    # --- Pending applications requiring attention ---
    # dept_status PENDING  OR  (dept APPROVED, mentor ACCEPTED, advisor still PENDING)
    coord_pending_applications = []
    for app in (
        InternshipApplication.objects.filter(
            student__in=student_ids,
        )
        .filter(
            Q(dept_status="PENDING")
            | Q(
                dept_status="APPROVED",
                mentor_status="ACCEPTED",
                advisor_status="PENDING",
            )
        )
        .select_related("student__user", "position__company")
        .order_by("-created_at")
    ):
        coord_pending_applications.append(
            {
                "application_id": app.id,
                "student_name": app.student.user.get_full_name()
                or app.student.user.username,
                "position_title": app.position.title,
                "company_name": app.position.company.company_name,
                "dept_status": app.dept_status,
                "mentor_status": app.mentor_status,
                "advisor_status": app.advisor_status,
                "applied_at": app.created_at,
            }
        )

    return {
        "department": department.department_name,
        "students_count": student_count,
        "advisors_count": advisor_count,
        "internship_counts": int_counts,
        "placement_rate": placement_rate,
        "placed_students": placed,
        "pending_reports": pending_reports,
        "advisor_workload": advisor_workload,
        "attendance_flags": attendance_flags,
        "applied_students": coord_applied_students,
        "active_interns": coord_active_interns,
        "pending_applications": coord_pending_applications,
    }


# ---------------------------------------------------------------------------
# Admin dashboard
# ---------------------------------------------------------------------------


def get_admin_dashboard() -> dict:
    """Return global system statistics for admin users."""
    # Role-based user counts in one query
    role_counts = {
        row["role_name"]: row["cnt"]
        for row in UserRole.objects.annotate(cnt=Count("user")).values(
            "role_name", "cnt"
        )
    }

    total_users = User.objects.count()

    # Internship breakdown
    int_counts = Internship.objects.aggregate(
        total=Count("id"),
        ongoing=Count("id", filter=Q(status="ONGOING")),
        completed=Count("id", filter=Q(status="COMPLETED")),
        cancelled=Count("id", filter=Q(status="CANCELLED")),
        not_started=Count("id", filter=Q(status="NOT_STARTED")),
    )

    return {
        "users": {
            "total": total_users,
            "students": role_counts.get("STUDENT", 0),
            "advisors": role_counts.get("ADVISOR", 0),
            "coordinators": role_counts.get("COORDINATOR", 0),
            "company_mentors": role_counts.get("COMPANY", 0),
            "admins": role_counts.get("ADMIN", 0),
        },
        "companies": Company.objects.count(),
        "internship_positions": InternshipPosition.objects.count(),
        "internships": int_counts,
        "reports_submitted": Report.objects.count(),
        "evaluations": {
            "advisor_evaluations_completed": AdvisorEvaluation.objects.filter(
                submitted_at__isnull=False
            ).count(),
            "industry_evaluations_completed": FinalIndustryEvaluation.objects.filter(
                submitted_at__isnull=False
            ).count(),
        },
    }
