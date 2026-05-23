"""
Attendance service layer.

Business rules for check-in location validation live here, not in views.
"""

from rest_framework.exceptions import ValidationError

from core.utils import haversine_distance


def validate_location_for_checkin(position, latitude, longitude, accuracy):
    """
    Validate GPS data against the position's work_mode.

    Returns
    -------
    is_location_verified : bool

    Raises
    ------
    ValidationError
        For ONSITE positions when coordinates are missing or out of range.
    """
    work_mode = getattr(position, "work_mode", "ONSITE")

    # ---- REMOTE: no strict location validation ----
    if work_mode == "REMOTE":
        # Accept with or without coordinates; always mark verified
        return True

    # ---- ONSITE: GPS required & distance enforced ----
    if work_mode == "ONSITE":
        if latitude is None or longitude is None:
            raise ValidationError(
                "Latitude and longitude are required for onsite internships."
            )

        has_work_location = (
            position.work_latitude is not None
            and position.work_longitude is not None
        )

        if not has_work_location:
            # Position has no reference coordinates set — accept but flag unverified
            return False

        gps_accurate = accuracy is not None and accuracy <= 50

        if not gps_accurate:
            raise ValidationError(
                "GPS accuracy is too low for onsite attendance verification. "
                "Ensure accuracy is within 50 meters."
            )

        distance = haversine_distance(
            latitude,
            longitude,
            position.work_latitude,
            position.work_longitude,
        )

        if distance > position.allowed_radius_meters:
            raise ValidationError(
                f"You are {int(distance)}m away from the work location. "
                f"Must be within {position.allowed_radius_meters}m."
            )

        return True

    # ---- HYBRID: GPS optional, verify when provided ----
    if latitude is not None and longitude is not None:
        has_work_location = (
            position.work_latitude is not None
            and position.work_longitude is not None
        )
        if has_work_location:
            gps_accurate = accuracy is not None and accuracy <= 50
            if gps_accurate:
                distance = haversine_distance(
                    latitude,
                    longitude,
                    position.work_latitude,
                    position.work_longitude,
                )
                return distance <= position.allowed_radius_meters
        return False

    # Hybrid without coordinates — accepted but unverified
    return False
