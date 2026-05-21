"""
Reusable notification service.

All code that wants to create a notification should call
`create_notification()` from here.  Never duplicate this
logic directly inside views or signals.
"""

import logging

logger = logging.getLogger(__name__)


def create_notification(
    recipient,
    title: str,
    message: str,
    notification_type: str = "GENERAL",
    related_object_id: int | None = None,
    related_object_type: str = "",
):
    """
    Create and persist a Notification for *recipient*.

    Parameters
    ----------
    recipient : AUTH_USER_MODEL instance
        The user who will receive the notification.
    title : str
        Short summary shown in the notification list.
    message : str
        Full notification body.
    notification_type : str
        One of Notification.NotificationType choices.
        Defaults to 'GENERAL'.
    related_object_id : int | None
        Optional PK of the related model instance.
    related_object_type : str
        Optional string name of the related model (e.g. 'Internship').

    Returns
    -------
    Notification | None
        The created instance, or None if creation fails.
    """
    # Import here to avoid circular-import issues at module load time
    from core.models import Notification

    try:
        return Notification.objects.create(
            recipient=recipient,
            title=title,
            message=message,
            notification_type=notification_type,
            related_object_id=related_object_id,
            related_object_type=related_object_type or "",
        )
    except Exception:
        logger.exception(
            "Failed to create notification for user %s — title: %s",
            getattr(recipient, "email", recipient),
            title,
        )
        return None
