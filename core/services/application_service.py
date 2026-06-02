"""
Application workflow service layer.

All business logic for the internship application lifecycle lives here.
Views must be thin — delegate all workflow transitions to these functions.
"""

import logging

from django.utils import timezone

from core.services.audit_service import log_audit_event
from core.services.notification_service import create_notification

logger = logging.getLogger(__name__)


def build_form_snapshot(
    student,
    position,
    requested_start_date=None,
    requested_end_date=None,
    working_days_per_week=None,
    working_hours_per_day=None,
):
    """
    Build an immutable snapshot of student/company/mentor data at application time.
    Stored in InternshipApplication.form_snapshot so future edits never alter history.
    """
    company = position.company
    user = student.user
    department = student.department

    # Mentor info (company has OneToOne mentor)
    mentor = getattr(company, "mentor", None)

    resume_url = None
    if student.resume:
        try:
            resume_url = student.resume.url
        except Exception:
            resume_url = None

    return {
        "student": {
            "name": user.get_full_name() or user.username,
            "student_id": student.student_id,
            "college": department.college or "",
            "department": department.department_name,
            "mobile": user.phone or "",
            "email": user.email,
            "resume_url": resume_url,
        },
        "company": {
            "name": company.company_name,
            "mailing_address": company.address or "",
            "physical_address": company.address or "",
            "phone": company.contact_phone or "",
            "website": company.website or "",
            "email": company.contact_email or "",
        },
        "mentor": {
            "name": (
                mentor.user.get_full_name() or mentor.user.username if mentor else ""
            ),
            "designation": mentor.position if mentor else "",
            "phone": mentor.user.phone if mentor else "",
            "email": mentor.user.email if mentor else "",
        },
        "internship": {
            "position_title": position.title,
            "work_mode": position.work_mode,
            "requested_start_date": str(requested_start_date)
            if requested_start_date
            else None,
            "requested_end_date": str(requested_end_date)
            if requested_end_date
            else None,
            "working_days_per_week": working_days_per_week,
            "working_hours_per_day": str(working_hours_per_day)
            if working_hours_per_day
            else None,
        },
    }


def process_coordinator_review(application, actor, action: str, signature: str = ""):
    """
    Process coordinator (department) review of an internship application.

    Parameters
    ----------
    application : InternshipApplication
    actor : User — the coordinator performing the review
    action : "approve" | "reject"
    signature : str — coordinator's full name as signature (optional)

    Raises
    ------
    ValueError if action is invalid or application is not in PENDING state.
    """
    if application.dept_status != "PENDING":
        raise ValueError("Application has already been reviewed by the coordinator.")

    if application.mentor_status != "ACCEPTED":
        raise ValueError(
            "This application must be accepted by the company mentor before coordinator review."
        )

    if action not in ("approve", "reject"):
        raise ValueError("Action must be 'approve' or 'reject'.")

    now = timezone.now()

    if action == "approve":
        application.dept_status = "APPROVED"
        application.coordinator_signature = signature or (
            actor.get_full_name() or actor.username
        )
        application.coordinator_signed_at = now
        application.save(
            update_fields=[
                "dept_status",
                "coordinator_signature",
                "coordinator_signed_at",
            ]
        )

        # Notify the company mentor
        company_mentor = getattr(application.position.company, "mentor", None)
        if company_mentor:
            create_notification(
                recipient=company_mentor.user,
                title="New Internship Application to Review",
                message=(
                    f"Student {application.student.user.get_full_name() or application.student.user.email} "
                    f"has applied for '{application.position.title}'. Please review."
                ),
                notification_type="INTERNSHIP_STATUS_CHANGED",
                related_object_id=application.id,
                related_object_type="InternshipApplication",
            )

        # Notify student
        create_notification(
            recipient=application.student.user,
            title="Application Approved by Coordinator",
            message=(
                f"Your application for '{application.position.title}' has been approved "
                f"by the department coordinator and forwarded to the company."
            ),
            notification_type="INTERNSHIP_STATUS_CHANGED",
            related_object_id=application.id,
            related_object_type="InternshipApplication",
        )

    else:  # reject
        application.dept_status = "REJECTED"
        application.save(update_fields=["dept_status"])

        create_notification(
            recipient=application.student.user,
            title="Application Rejected by Coordinator",
            message=(
                f"Your application for '{application.position.title}' has been "
                f"rejected by the department coordinator."
            ),
            notification_type="INTERNSHIP_STATUS_CHANGED",
            related_object_id=application.id,
            related_object_type="InternshipApplication",
        )

    log_audit_event(
        actor=actor,
        action="APPLICATION_COORDINATOR_REVIEWED",
        target_type="InternshipApplication",
        target_id=application.id,
        description=(
            f"Coordinator {actor.email} {action}d application {application.id} "
            f"for student {application.student.user.email}."
        ),
    )

    return application


def process_mentor_review(
    application, actor, action: str, signature: str = "", rejection_reason: str = ""
):
    """
    Process company mentor review of an internship application.

    Parameters
    ----------
    application : InternshipApplication
    actor : User — the mentor performing the review
    action : "accept" | "reject"
    signature : str — mentor's full name as signature
    rejection_reason : str — REQUIRED when action == "reject"

    Raises
    ------
    ValueError for invalid state or missing rejection_reason.
    """
    # Allow mentor to act even if the coordinator has not yet approved (mentor-first flow).
    # Only prevent mentor actions when coordinator has explicitly rejected the application.
    if application.dept_status == "REJECTED":
        raise ValueError("Application has been rejected by the coordinator.")

    if application.mentor_status not in (None, "PENDING"):
        raise ValueError("Application has already been reviewed by the mentor.")

    if action not in ("accept", "reject"):
        raise ValueError("Action must be 'accept' or 'reject'.")

    if action == "reject" and not rejection_reason.strip():
        raise ValueError(
            "A rejection reason is required when rejecting an application."
        )

    now = timezone.now()

    if action == "accept":
        from core.models import CompanyMentor

        mentor_obj = CompanyMentor.objects.filter(user=actor).first()
        application.mentor_status = "ACCEPTED"
        application.mentor = mentor_obj
        application.mentor_signature = signature or (
            actor.get_full_name() or actor.username
        )
        application.mentor_signed_at = now
        application.save(
            update_fields=[
                "mentor_status",
                "mentor",
                "mentor_signature",
                "mentor_signed_at",
            ]
        )

        create_notification(
            recipient=application.student.user,
            title="Internship Offer Received",
            message=(
                f"Congratulations! Your application for '{application.position.title}' at "
                f"'{application.position.company.company_name}' has been accepted. "
                f"Please confirm your acceptance."
            ),
            notification_type="INTERNSHIP_STATUS_CHANGED",
            related_object_id=application.id,
            related_object_type="InternshipApplication",
        )

    else:  # reject
        application.mentor_status = "REJECTED"
        application.rejection_reason = rejection_reason.strip()
        application.save(update_fields=["mentor_status", "rejection_reason"])

        create_notification(
            recipient=application.student.user,
            title="Internship Application Rejected by Company",
            message=(
                f"Your application for '{application.position.title}' at "
                f"'{application.position.company.company_name}' was rejected. "
                f"Reason: {rejection_reason.strip()}"
            ),
            notification_type="INTERNSHIP_STATUS_CHANGED",
            related_object_id=application.id,
            related_object_type="InternshipApplication",
        )

    log_audit_event(
        actor=actor,
        action="APPLICATION_MENTOR_REVIEWED",
        target_type="InternshipApplication",
        target_id=application.id,
        description=(
            f"Mentor {actor.email} {action}ed application {application.id} "
            f"for student {application.student.user.email}."
            + (f" Reason: {rejection_reason.strip()}" if action == "reject" else "")
        ),
    )

    return application


def process_student_confirmation(application, actor, decision: str):
    """
    Process student's final confirmation of internship offer.

    Parameters
    ----------
    application : InternshipApplication
    actor : User — the student
    decision : "accept" | "decline"

    Raises
    ------
    ValueError for invalid state.
    """
    if application.dept_status != "APPROVED":
        raise ValueError("Coordinator has not approved this application yet.")

    if application.mentor_status != "ACCEPTED":
        raise ValueError("Company mentor has not accepted this application yet.")

    if application.student_decision != "PENDING":
        raise ValueError("You have already made a decision on this offer.")

    if decision not in ("accept", "decline"):
        raise ValueError("Decision must be 'accept' or 'decline'.")

    if decision == "accept":
        application.student_decision = "ACCEPTED"
        application.save(update_fields=["student_decision"])

        log_audit_event(
            actor=actor,
            action="OFFER_ACCEPTED",
            target_type="InternshipApplication",
            target_id=application.id,
            description=f"Student {actor.email} accepted offer for application {application.id}.",
        )

    else:
        application.student_decision = "DECLINED"
        application.save(update_fields=["student_decision"])

        log_audit_event(
            actor=actor,
            action="OFFER_DECLINED",
            target_type="InternshipApplication",
            target_id=application.id,
            description=f"Student {actor.email} declined offer for application {application.id}.",
        )

    # Notify the coordinator and mentor
    coordinator_msg = (
        f"Student {actor.get_full_name() or actor.email} has "
        f"{'accepted' if decision == 'accept' else 'declined'} the internship offer "
        f"for '{application.position.title}'."
    )
    if application.mentor:
        create_notification(
            recipient=application.mentor.user,
            title=f"Student {'Accepted' if decision == 'accept' else 'Declined'} Offer",
            message=coordinator_msg,
            notification_type="INTERNSHIP_STATUS_CHANGED",
            related_object_id=application.id,
            related_object_type="InternshipApplication",
        )

    return application
