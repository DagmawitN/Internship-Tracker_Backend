"""
Analytics service layer.

Functions aggregate data across all users/departments/companies.
Call only from views.  Do not call from other views directly.
"""

import logging

from django.db.models import Avg, Count, Q

from core.models import (
    Advisor,
    AdvisorEvaluation,
    Company,
    Department,
    FinalIndustryEvaluation,
    Internship,
    InternshipApplication,
    Report,
    Student,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Placement analytics
# ---------------------------------------------------------------------------


def get_placement_analytics(
    department_id=None,
    year=None,
    company_id=None,
) -> dict:
    """
    Return placement statistics.

    'Placed' means the student has an Internship record that is not CANCELLED.
    Filters: department, start year, company.
    """
    qs = Internship.objects.exclude(status="CANCELLED").select_related(
        "student__department", "company"
    )

    if department_id:
        qs = qs.filter(student__department_id=department_id)
    if company_id:
        qs = qs.filter(company_id=company_id)
    if year:
        qs = qs.filter(start_date__year=year)

    total_placed = qs.count()

    # Denominator – total students (filtered by dept if applicable)
    students_qs = Student.objects.all()
    if department_id:
        students_qs = students_qs.filter(department_id=department_id)
    total_students = students_qs.count()

    placement_rate = (
        round((total_placed / total_students) * 100, 1) if total_students else 0.0
    )

    # By status
    by_status = qs.aggregate(
        ongoing=Count("id", filter=Q(status="ONGOING")),
        completed=Count("id", filter=Q(status="COMPLETED")),
        not_started=Count("id", filter=Q(status="NOT_STARTED")),
    )

    # By department (top 20)
    by_department = list(
        qs.values("student__department__department_name")
        .annotate(count=Count("id"))
        .order_by("-count")[:20]
    )

    # By company (top 10)
    by_company = list(
        qs.values("company__company_name")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )

    # By year (group by start_date year)
    by_year = list(
        qs.filter(start_date__isnull=False)
        .values("start_date__year")
        .annotate(count=Count("id"))
        .order_by("start_date__year")
    )

    return {
        "total_placed": total_placed,
        "total_students": total_students,
        "placement_rate": placement_rate,
        "by_status": by_status,
        "by_department": by_department,
        "by_company": by_company,
        "by_year": by_year,
    }


# ---------------------------------------------------------------------------
# Company performance
# ---------------------------------------------------------------------------


def get_company_performance() -> list:
    """
    Return a list of company performance summaries, sorted by completion rate.
    Uses annotated queries to avoid per-company N+1 on internship counts.
    """
    companies = (
        Company.objects.filter(is_active=True)
        .annotate(
            total_internships=Count("internships", distinct=True),
            ongoing=Count(
                "internships",
                filter=Q(internships__status="ONGOING"),
                distinct=True,
            ),
            completed=Count(
                "internships",
                filter=Q(internships__status="COMPLETED"),
                distinct=True,
            ),
            cancelled=Count(
                "internships",
                filter=Q(internships__status="CANCELLED"),
                distinct=True,
            ),
        )
        .order_by("-completed")
    )

    results = []
    for company in companies:
        total = company.total_internships or 0
        non_cancelled = total - (company.cancelled or 0)
        completion_rate = (
            round((company.completed / non_cancelled) * 100, 1)
            if non_cancelled
            else 0.0
        )

        # Average industry evaluation score – one extra query per company
        # (acceptable; companies are not expected to be in the thousands)
        avg_eval = FinalIndustryEvaluation.objects.filter(
            internship__position__company=company
        ).aggregate(avg=Avg("overall_student_performance"))["avg"]

        avg_advisor_eval = AdvisorEvaluation.objects.filter(
            internship__position__company=company
        ).aggregate(avg=Avg("weighted_score"))["avg"]

        results.append(
            {
                "company_id": company.id,
                "company_name": company.company_name,
                "industry_type": company.industry_type,
                "total_internships": total,
                "ongoing": company.ongoing,
                "completed": company.completed,
                "cancelled": company.cancelled,
                "completion_rate": completion_rate,
                "avg_industry_eval_score": (
                    round(float(avg_eval), 2) if avg_eval is not None else None
                ),
                "avg_advisor_eval_score": (
                    round(float(avg_advisor_eval), 2)
                    if avg_advisor_eval is not None
                    else None
                ),
            }
        )

    # Sort highest completion rate first
    results.sort(key=lambda x: x["completion_rate"], reverse=True)
    return results


# ---------------------------------------------------------------------------
# Department statistics
# ---------------------------------------------------------------------------


def get_department_statistics(department_id=None) -> list:
    """
    Return per-department statistics.
    If department_id is provided, returns only that department's data.
    """
    depts_qs = Department.objects.annotate(
        student_count=Count("students", distinct=True),
        advisor_count=Count("advisors", distinct=True),
    ).order_by("department_name")

    if department_id:
        depts_qs = depts_qs.filter(id=department_id)

    results = []
    for dept in depts_qs:
        student_ids = list(
            Student.objects.filter(department=dept).values_list("id", flat=True)
        )

        if not student_ids:
            results.append(
                {
                    "department_id": dept.id,
                    "department_name": dept.department_name,
                    "college": dept.college,
                    "student_count": 0,
                    "advisor_count": dept.advisor_count,
                    "active_internships": 0,
                    "completed_internships": 0,
                    "cancelled_internships": 0,
                    "placement_rate": 0.0,
                    "completion_rate": 0.0,
                    "placed_students": 0,
                    "reports": {"total": 0, "submitted": 0, "reviewed": 0},
                }
            )
            continue

        # Internship breakdown (single aggregated query per dept)
        int_counts = Internship.objects.filter(student__in=student_ids).aggregate(
            total=Count("id"),
            active=Count("id", filter=Q(status="ONGOING")),
            completed=Count("id", filter=Q(status="COMPLETED")),
            cancelled=Count("id", filter=Q(status="CANCELLED")),
        )

        total_ints = int_counts["total"] or 0
        cancelled = int_counts["cancelled"] or 0
        completed = int_counts["completed"] or 0
        placed = total_ints - cancelled
        non_cancelled = placed

        placement_rate = (
            round((placed / dept.student_count) * 100, 1) if dept.student_count else 0.0
        )
        completion_rate = (
            round((completed / non_cancelled) * 100, 1) if non_cancelled else 0.0
        )

        # Report stats
        app_ids = list(
            InternshipApplication.objects.filter(
                student__in=student_ids, student_decision="ACCEPTED"
            ).values_list("id", flat=True)
        )
        report_counts = Report.objects.filter(internship__in=app_ids).aggregate(
            total=Count("id"),
            submitted=Count("id", filter=Q(status="SUBMITTED")),
            reviewed=Count("id", filter=Q(status="REVIEWED")),
        )

        results.append(
            {
                "department_id": dept.id,
                "department_name": dept.department_name,
                "college": dept.college,
                "student_count": dept.student_count,
                "advisor_count": dept.advisor_count,
                "active_internships": int_counts["active"] or 0,
                "completed_internships": completed,
                "cancelled_internships": cancelled,
                "placement_rate": placement_rate,
                "completion_rate": completion_rate,
                "placed_students": placed,
                "reports": report_counts,
            }
        )

    return results
