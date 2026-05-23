"""
Centralized audit logging service.

All code that wants to record an audit event should call
`log_audit_event()` from here.  Never duplicate this logic
directly inside views or signals.
"""

import logging

from django.utils import timezone

logger = logging.getLogger(__name__)


def log_audit_event(
    *,
    actor,
    action: str,
    target_type: str = "",
    target_id: int | None = None,
    description: str = "",
):
    """
    Persist an AuditLog row.

    Parameters
    ----------
    actor : User instance (or None for system-level actions)
    action : short verb, e.g. "INTERNSHIP_CREATED"
    target_type : model name string, e.g. "Internship"
    target_id : PK of affected object
    description : human-readable detail
    """
    from core.models import AuditLog

    try:
        return AuditLog.objects.create(
            actor=actor,
            action=action,
            target_type=target_type,
            target_id=target_id,
            description=description,
            timestamp=timezone.now(),
        )
    except Exception:
        logger.exception(
            "Failed to create audit log — action=%s actor=%s target=%s:%s",
            action,
            getattr(actor, "email", actor),
            target_type,
            target_id,
        )
        return None
