"""Reusable validation for internship evaluation score fields."""

from django.core.exceptions import ValidationError

from core.evaluation_constants import (
    ADVISOR_SCORE_FIELDS,
    EXAMINER_SCORE_FIELDS,
    LOGBOOK_SCORE_FIELDS,
    PERFORMANCE_SCORE_FIELDS,
    REPORT_SCORE_FIELDS,
)


def _validate_score_map(instance, field_limits, section_label):
    errors = {}
    for field_name, max_score in field_limits.items():
        value = getattr(instance, field_name, None)
        if value is None:
            continue
        if value < 0:
            errors[field_name] = "Score cannot be negative."
        
    if errors:
        raise ValidationError(errors)


def validate_advisor_score_fields(instance):
    _validate_score_map(instance, REPORT_SCORE_FIELDS, "report section")
    _validate_score_map(instance, LOGBOOK_SCORE_FIELDS, "logbook section")
    _validate_score_map(instance, PERFORMANCE_SCORE_FIELDS, "performance section")


def validate_examiner_score_fields(instance):
    _validate_score_map(instance, EXAMINER_SCORE_FIELDS, "examiner evaluation")


def validate_advisor_assignment(user, internship):
    """Ensure user is the assigned advisor for the internship application."""
    from core.models import Advisor, AdvisorAssignment

    if internship is None:
        raise ValidationError({"internship": "Internship application is required."})

    if AdvisorAssignment.objects.filter(
        internship=internship, advisor=user, role="ADVISOR"
    ).exists():
        return

    advisor_profile = Advisor.objects.filter(user=user).first()
    if advisor_profile and internship.student.advisor_id == advisor_profile.pk:
        return
    if internship.advisor_id and internship.advisor.user_id == user.id:
        return

    raise ValidationError(
        "Only the advisor assigned to this internship can perform this action."
    )


def validate_examiner_assignment(user, internship):
    """Ensure user is an assigned examiner for the internship application."""
    from core.models import AdvisorAssignment

    if internship is None:
        raise ValidationError({"internship": "Internship application is required."})

    if AdvisorAssignment.objects.filter(
        internship=internship, advisor=user, role="EXAMINER"
    ).exists():
        return

    raise ValidationError(
        "Only an examiner assigned to this internship can perform this action."
    )


def validate_internship_prerequisites_for_advisor_eval(internship):
    """Require final report and at least one submitted logbook before advisor approval."""
    from core.models import Report, WeeklyLogbook

    errors = []
    final_report = Report.objects.filter(
        internship=internship, report_type="FINAL"
    ).first()
    if not final_report:
        errors.append("Final internship report must be submitted.")
    elif final_report.status not in (
        "SUBMITTED",
        "EXAMINER_APPROVED",
        "ADVISOR_APPROVED",
        "REVIEWED",
        "APPROVED",
    ):
        errors.append(
            "Final report must be submitted and reviewed by examiner."
        )

    logbook_count = WeeklyLogbook.objects.filter(
        internship=internship,
        status__in=("SUBMITTED", "VERIFIED", "REVIEWED", "COMPANY_VERIFIED", "APPROVED"),
    ).count()
    if logbook_count == 0:
        errors.append("At least one weekly logbook must be submitted.")

    if errors:
        raise ValidationError({"prerequisites": errors})
