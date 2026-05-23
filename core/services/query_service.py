"""
Role-scoped queryset helpers.

These helpers ensure that dashboards, exports, and views all share
the same access-control logic.  Never duplicate role-based filtering
in individual views — call these helpers instead.
"""

import logging

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

logger = logging.getLogger(__name__)


def _role_name(user):
    return getattr(user.role, "role_name", None) if user.role else None


# ---------------------------------------------------------------------------
# Internships
# ---------------------------------------------------------------------------

def get_user_internships_queryset(user):
    """Return Internship queryset scoped to the user's role."""
    role = _role_name(user)
    base = Internship.objects.select_related(
        "student__user",
        "student__department",
        "student__advisor__user",
        "position",
        "position__company",
        "company",
        "mentor__user",
    )

    if role == "STUDENT":
        return base.filter(student__user=user)

    if role == "ADVISOR":
        return base.filter(student__advisor__user=user)

    if role == "COMPANY":
        mentor = CompanyMentor.objects.filter(user=user).first()
        if not mentor:
            return base.none()
        return base.filter(company=mentor.company)

    if role == "COORDINATOR":
        staff = getattr(user, "staff", None)
        if not staff:
            return base.none()
        return base.filter(student__department=staff.department)

    if role == "ADMIN":
        return base.all()

    return base.none()


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------

def get_user_attendance_queryset(user):
    """Return Attendance queryset scoped to the user's role."""
    role = _role_name(user)
    base = Attendance.objects.select_related(
        "internship__position",
        "internship__position__company",
        "internship__student__user",
        "internship__student__department",
        "internship__company",
    )

    if role == "STUDENT":
        return base.filter(internship__student__user=user)

    if role == "ADVISOR":
        return base.filter(internship__student__advisor__user=user)

    if role == "COMPANY":
        mentor = CompanyMentor.objects.filter(user=user).first()
        if not mentor:
            return base.none()
        return base.filter(internship__company=mentor.company)

    if role == "COORDINATOR":
        staff = getattr(user, "staff", None)
        if not staff:
            return base.none()
        return base.filter(internship__student__department=staff.department)

    if role == "ADMIN":
        return base.all()

    return base.none()


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

def get_user_reports_queryset(user):
    """Return Report queryset scoped to the user's role."""
    role = _role_name(user)
    base = Report.objects.select_related(
        "internship__student__user",
        "internship__student__department",
        "internship__position__company",
    )

    if role == "STUDENT":
        return base.filter(internship__student__user=user)

    if role == "ADVISOR":
        return base.filter(internship__student__advisor__user=user)

    if role == "COORDINATOR":
        staff = getattr(user, "staff", None)
        if not staff:
            return base.none()
        return base.filter(internship__student__department=staff.department)

    if role == "ADMIN":
        return base.all()

    return base.none()


# ---------------------------------------------------------------------------
# Evaluations (advisor + industry combined)
# ---------------------------------------------------------------------------

def get_user_advisor_evaluations_queryset(user):
    """Return AdvisorEvaluation queryset scoped to the user's role."""
    role = _role_name(user)
    base = AdvisorEvaluation.objects.select_related(
        "internship__student__user",
        "internship__student__department",
        "internship__position__company",
    )

    if role == "STUDENT":
        return base.filter(internship__student__user=user)

    if role == "ADVISOR":
        return base.filter(internship__student__advisor__user=user)

    if role == "COORDINATOR":
        staff = getattr(user, "staff", None)
        if not staff:
            return base.none()
        return base.filter(internship__student__department=staff.department)

    if role == "ADMIN":
        return base.all()

    return base.none()


def get_user_industry_evaluations_queryset(user):
    """Return FinalIndustryEvaluation queryset scoped to the user's role."""
    role = _role_name(user)
    base = FinalIndustryEvaluation.objects.select_related(
        "internship__student__user",
        "internship__student__department",
        "internship__position__company",
    )

    if role == "STUDENT":
        return base.filter(internship__student__user=user)

    if role == "ADVISOR":
        return base.filter(internship__student__advisor__user=user)

    if role == "COMPANY":
        mentor = CompanyMentor.objects.filter(user=user).first()
        if not mentor:
            return base.none()
        return base.filter(internship__company=mentor.company)

    if role == "COORDINATOR":
        staff = getattr(user, "staff", None)
        if not staff:
            return base.none()
        return base.filter(internship__student__department=staff.department)

    if role == "ADMIN":
        return base.all()

    return base.none()


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

def get_user_applications_queryset(user):
    """Return InternshipApplication queryset scoped to the user's role."""
    role = _role_name(user)
    base = InternshipApplication.objects.select_related(
        "student__user",
        "student__department",
        "position",
        "position__company",
        "advisor__user",
    )

    if role == "STUDENT":
        return base.filter(student__user=user)

    if role == "ADVISOR":
        return base.filter(student__advisor__user=user)

    if role == "COORDINATOR":
        staff = getattr(user, "staff", None)
        if not staff:
            return base.none()
        return base.filter(student__department=staff.department)

    if role == "ADMIN":
        return base.all()

    return base.none()
