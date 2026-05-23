"""
Lifecycle service layer.

Orchestrates internship state transitions, notifications, and audit logging.
Views should delegate to these functions for any lifecycle changes.
"""

import logging
from decimal import Decimal

from django.db.models import Case, F, Sum, Value, When
from django.utils import timezone

from core.services.audit_service import log_audit_event
from core.services.notification_service import create_notification

logger = logging.getLogger(__name__)


def start_internships_for_position(position, actor):
    """
    Transition all NOT_STARTED internships for a position to ONGOING.

    Returns
    -------
    int : number of internships started
    """
    from core.models import Internship

    internships = Internship.objects.filter(
        position=position,
        status="NOT_STARTED",
    )

    if not internships.exists():
        return 0

    today = timezone.now().date()

    # Collect student users BEFORE bulk update for notification
    student_users = list(
        internships.select_related("student__user").values_list(
            "student__user_id", "student__user__email", flat=False
        )
    )

    updated = internships.update(
        status="ONGOING",
        start_date=Case(
            When(start_date__isnull=True, then=Value(today)),
            default=F("start_date"),
        ),
    )

    # Notify each affected student
    from django.contrib.auth import get_user_model
    User = get_user_model()

    for uid, _email in student_users:
        try:
            user = User.objects.get(pk=uid)
            create_notification(
                recipient=user,
                title="Internship Started",
                message=f"Your internship for '{position.title}' has started.",
                notification_type="INTERNSHIP_STATUS_CHANGED",
                related_object_id=position.id,
                related_object_type="InternshipPosition",
            )
        except User.DoesNotExist:
            pass

    log_audit_event(
        actor=actor,
        action="INTERNSHIPS_STARTED",
        target_type="InternshipPosition",
        target_id=position.id,
        description=f"Started {updated} internship(s) for position '{position.title}'.",
    )

    return updated


def complete_internship(internship, actor):
    """Mark an internship as COMPLETED, compute total hours, notify student."""
    from core.models import Attendance

    total_hours = Attendance.objects.filter(
        internship=internship,
    ).aggregate(total=Sum("total_hours"))["total"] or Decimal("0")

    internship.status = "COMPLETED"
    internship.end_date = timezone.now().date()
    internship.total_hours = total_hours
    internship.save(update_fields=["status", "end_date", "total_hours"])

    create_notification(
        recipient=internship.student.user,
        title="Internship Completed",
        message=f"Your internship for '{internship.position.title}' has been marked as completed.",
        notification_type="INTERNSHIP_STATUS_CHANGED",
        related_object_id=internship.id,
        related_object_type="Internship",
    )

    log_audit_event(
        actor=actor,
        action="INTERNSHIP_COMPLETED",
        target_type="Internship",
        target_id=internship.id,
        description=f"Internship completed. Total hours: {total_hours}.",
    )


def cancel_internship(internship, actor):
    """Cancel an internship, notify student."""
    today = timezone.now().date()
    internship.status = "CANCELLED"
    internship.end_date = today
    internship.save(update_fields=["status", "end_date"])

    create_notification(
        recipient=internship.student.user,
        title="Internship Cancelled",
        message=f"Your internship for '{internship.position.title}' has been cancelled.",
        notification_type="INTERNSHIP_STATUS_CHANGED",
        related_object_id=internship.id,
        related_object_type="Internship",
    )

    log_audit_event(
        actor=actor,
        action="INTERNSHIP_CANCELLED",
        target_type="Internship",
        target_id=internship.id,
        description=f"Internship for '{internship.position.title}' cancelled.",
    )
