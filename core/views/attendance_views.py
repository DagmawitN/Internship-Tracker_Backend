import math
from datetime import datetime, timedelta
from decimal import Decimal

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Attendance, CompanyMentor, Internship
from core.permissions import IsStudentUser
from core.serializers.attendance_serializer import (
    AttendanceNotesSerializer,
    AttendanceSerializer,
    CheckInSerializer,
    CheckOutSerializer,
)
from core.utils import haversine_distance

LATE_THRESHOLD_MINUTES = 30


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_role(user):
    return getattr(user.role, "role_name", None) if user.role else None


def _attendance_queryset_for_user(user):
    """Return the Attendance queryset the requesting user is allowed to see."""
    role = _get_role(user)

    if role == "STUDENT":
        return Attendance.objects.filter(internship__student__user=user).select_related(
            "internship__position", "internship__student__user"
        )

    if role == "COMPANY":
        mentor = CompanyMentor.objects.filter(user=user).first()
        if not mentor:
            return Attendance.objects.none()
        return Attendance.objects.filter(
            internship__company=mentor.company
        ).select_related("internship__position", "internship__student__user")

    if role == "COORDINATOR":
        staff = getattr(user, "staff", None)
        if not staff:
            return Attendance.objects.none()
        return Attendance.objects.filter(
            internship__student__department=staff.department
        ).select_related("internship__position", "internship__student__user")

    if role == "ADMIN":
        return Attendance.objects.all().select_related(
            "internship__position", "internship__student__user"
        )

    return Attendance.objects.none()


# ---------------------------------------------------------------------------
# Check-In
# ---------------------------------------------------------------------------


class CheckInView(APIView):
    permission_classes = [IsAuthenticated, IsStudentUser]
    serializer_class = CheckInSerializer

    def post(self, request):
        serializer = CheckInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        internship = get_object_or_404(
            Internship,
            pk=data["internship_id"],
            student__user=request.user,
        )

        # 1. Must be ONGOING
        if internship.status != "ONGOING":
            raise ValidationError(
                "Attendance can only be recorded for ongoing internships."
            )

        position = internship.position
        today = timezone.localdate()

        # 2. Validate working day
        today_name = today.strftime("%A").upper()
        working_days = position.working_days or []
        if working_days and today_name not in [d.upper() for d in working_days]:
            raise ValidationError(
                f"Today ({today_name.capitalize()}) is not a scheduled workday."
            )

        # 3. Prevent duplicate
        if Attendance.objects.filter(internship=internship, date=today).exists():
            raise ValidationError("Attendance already recorded for today.")

        now = timezone.localtime()
        check_in_time = now.time()

        # 4. GPS / location verification
        latitude = data.get("latitude")
        longitude = data.get("longitude")
        accuracy = data.get("accuracy")
        is_location_verified = False

        if position.is_remote:
            is_location_verified = True
        elif latitude is not None and longitude is not None:
            gps_accurate = accuracy is not None and accuracy <= 50
            has_work_location = (
                position.work_latitude is not None
                and position.work_longitude is not None
            )
            if gps_accurate and has_work_location:
                distance = haversine_distance(
                    latitude,
                    longitude,
                    position.work_latitude,
                    position.work_longitude,
                )
                is_location_verified = distance <= position.allowed_radius_meters

        # 5. Late detection
        attendance_status = Attendance.Status.PRESENT
        if position.daily_start_time:
            start_dt = datetime.combine(today, position.daily_start_time)
            late_threshold = start_dt + timedelta(minutes=LATE_THRESHOLD_MINUTES)
            check_in_dt = datetime.combine(today, check_in_time)
            if check_in_dt > late_threshold:
                attendance_status = Attendance.Status.LATE

        attendance = Attendance.objects.create(
            internship=internship,
            date=today,
            check_in_time=check_in_time,
            status=attendance_status,
            notes=data.get("notes", ""),
            latitude=latitude,
            longitude=longitude,
            accuracy=accuracy,
            is_location_verified=is_location_verified,
        )

        return Response(
            {
                "message": "Checked in successfully.",
                "attendance_id": attendance.id,
                "date": str(attendance.date),
                "check_in_time": str(attendance.check_in_time),
                "status": attendance.status,
                "is_location_verified": attendance.is_location_verified,
            },
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# Check-Out
# ---------------------------------------------------------------------------


class CheckOutView(APIView):
    permission_classes = [IsAuthenticated, IsStudentUser]
    serializer_class = CheckOutSerializer

    def post(self, request):
        serializer = CheckOutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        internship = get_object_or_404(
            Internship,
            pk=data["internship_id"],
            student__user=request.user,
        )

        today = timezone.localdate()
        attendance = Attendance.objects.filter(
            internship=internship, date=today
        ).first()

        if not attendance:
            raise ValidationError("No check-in found for today.")

        if attendance.check_out_time:
            raise ValidationError("Already checked out for today.")

        now = timezone.localtime()
        check_out_time = now.time()

        # Total hours calculation
        check_in_dt = datetime.combine(today, attendance.check_in_time)
        check_out_dt = datetime.combine(today, check_out_time)
        duration = check_out_dt - check_in_dt
        hours = Decimal(str(round(duration.total_seconds() / 3600, 2)))
        attendance.check_out_time = check_out_time
        attendance.total_hours = max(hours, Decimal("0"))
        attendance.save(update_fields=["check_out_time", "total_hours"])

        return Response(
            {
                "message": "Checked out successfully.",
                "attendance_id": attendance.id,
                "check_out_time": str(attendance.check_out_time),
                "total_hours": str(attendance.total_hours),
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# List + Detail
# ---------------------------------------------------------------------------


class AttendanceListView(generics.ListAPIView):
    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return _attendance_queryset_for_user(self.request.user).order_by(
            "-date", "-created_at"
        )


class AttendanceDetailView(generics.RetrieveAPIView):
    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        qs = _attendance_queryset_for_user(self.request.user)
        return get_object_or_404(qs, pk=self.kwargs["pk"])


# ---------------------------------------------------------------------------
# Notes Update
# ---------------------------------------------------------------------------


class AttendanceNotesUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AttendanceNotesSerializer

    def patch(self, request, pk):
        attendance = get_object_or_404(Attendance, pk=pk)
        user = request.user
        role = _get_role(user)

        if role == "STUDENT":
            if attendance.internship.student.user != user:
                raise PermissionDenied("Not your attendance record.")
        elif role == "COMPANY":
            mentor = CompanyMentor.objects.filter(user=user).first()
            if not mentor or attendance.internship.company != mentor.company:
                raise PermissionDenied("Not authorized.")
        elif role == "COORDINATOR":
            staff = getattr(user, "staff", None)
            if (
                not staff
                or attendance.internship.student.department != staff.department
            ):
                raise PermissionDenied("Not authorized.")
        elif role != "ADMIN":
            raise PermissionDenied("Not authorized.")

        serializer = AttendanceNotesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attendance.notes = serializer.validated_data["notes"]
        attendance.save(update_fields=["notes"])

        return Response(
            {
                "message": "Notes updated.",
                "attendance_id": attendance.id,
                "notes": attendance.notes,
            },
            status=status.HTTP_200_OK,
        )
