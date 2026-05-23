"""
Resume views.

Student-owned endpoints (own resume):
  GET  /students/me/resume/           — metadata
  POST /students/me/resume/           — upload / replace
  GET  /students/me/resume/download/  — returns a Cloudinary download URL

Authorized-staff endpoints (read-only, another student's resume):
  GET  /students/{pk}/resume/          — metadata
  GET  /students/{pk}/resume/download/ — returns a Cloudinary download URL

Authorized viewers of a student's resume
-----------------------------------------
  - The student themselves
  - Their assigned advisor
  - A coordinator of their department (via Staff model)
  - A company mentor whose company the student has applied to
  - Admin
"""

import logging
import os

import cloudinary.utils
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import CompanyMentor, InternshipApplication, Student
from core.permissions import IsStudentUser
from core.services.audit_service import log_audit_event

logger = logging.getLogger(__name__)

ALLOWED_RESUME_EXTENSIONS = {".pdf", ".docx"}
MAX_RESUME_SIZE_MB = 5


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate_resume_file(file):
    """Raise ValidationError for unsupported type or oversized files."""
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_RESUME_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file type '{ext}'. Only PDF and DOCX are allowed."
        )
    max_bytes = MAX_RESUME_SIZE_MB * 1024 * 1024
    if file.size > max_bytes:
        raise ValidationError(
            f"File too large. Maximum size is {MAX_RESUME_SIZE_MB} MB."
        )


def _delete_old_resume(student):
    """
    Remove an existing resume from Cloudinary via the storage backend's own
    delete() method (RawMediaCloudinaryStorage calls destroy with resource_type="raw").
    Non-fatal — logs a warning and continues on failure.
    """
    if not student.resume or not student.resume.name:
        return
    try:
        student.resume.storage.delete(student.resume.name)
    except Exception:
        logger.warning(
            "Could not delete old resume '%s' for student %s.",
            student.resume.name,
            student.id,
        )


def _build_resume_url(name: str) -> str | None:
    """Return the plain Cloudinary URL for a raw file (for display / metadata)."""
    if not name:
        return None
    try:
        url, _ = cloudinary.utils.cloudinary_url(name, resource_type="raw")
        return url
    except Exception:
        logger.warning("Could not build Cloudinary URL for '%s'.", name)
        return None


def _build_download_url(name: str) -> str | None:
    """
    Return a Cloudinary URL with the fl_attachment flag set so the browser
    treats the file as a download rather than opening it inline.
    """
    if not name:
        return None
    try:
        url, _ = cloudinary.utils.cloudinary_url(
            name,
            resource_type="raw",
            flags="attachment",
        )
        return url
    except Exception:
        logger.warning("Could not build Cloudinary download URL for '%s'.", name)
        return None


def _resume_metadata(student) -> dict:
    """Return the standard resume metadata dict for any student."""
    if not student.resume or not student.resume.name:
        return {
            "has_resume": False,
            "resume_url": None,
            "file_name": None,
            "uploaded_at": None,
        }
    return {
        "has_resume": True,
        "resume_url": _build_resume_url(student.resume.name),
        "file_name": student.resume.name.split("/")[-1],
        "uploaded_at": student.resume_uploaded_at,
    }


def _can_access_student_resume(requesting_user, student: Student) -> bool:
    """
    Return True if requesting_user is allowed to read this student's resume.

    Authorized parties
    ------------------
    - The student themselves
    - Their assigned advisor
    - A coordinator of their department (linked via Staff model)
    - A company mentor whose company the student has applied to
    - Admin
    """
    role = (
        getattr(requesting_user.role, "role_name", None)
        if requesting_user.role
        else None
    )

    if role == "ADMIN":
        return True

    # Student: own resume only
    own_profile = getattr(requesting_user, "student_profile", None)
    if own_profile is not None:
        return own_profile.id == student.id

    # Advisor: must be this student's assigned advisor
    if role == "ADVISOR":
        return (
            student.advisor_id is not None
            and student.advisor.user_id == requesting_user.id
        )

    # Coordinator: must belong to the same department (via Staff)
    if role == "COORDINATOR":
        staff = getattr(requesting_user, "staff", None)
        return staff is not None and staff.department_id == student.department_id

    # Company mentor: student must have at least one application to their company
    if role == "COMPANY":
        mentor = CompanyMentor.objects.filter(user=requesting_user).first()
        if mentor:
            return InternshipApplication.objects.filter(
                student=student,
                position__company=mentor.company,
            ).exists()

    return False


# ---------------------------------------------------------------------------
# Student-owned resume endpoints  (/students/me/resume/...)
# ---------------------------------------------------------------------------


class StudentResumeView(APIView):
    """
    GET  /students/me/resume/ — resume metadata for the logged-in student
    POST /students/me/resume/ — upload or replace resume (PDF / DOCX, ≤5 MB)
    """

    permission_classes = [IsAuthenticated, IsStudentUser]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        student = request.user.student_profile
        return Response(_resume_metadata(student), status=status.HTTP_200_OK)

    def post(self, request):
        student = request.user.student_profile

        resume_file = request.FILES.get("resume")
        if not resume_file:
            raise ValidationError("No file provided. Use the key 'resume'.")

        _validate_resume_file(resume_file)
        _delete_old_resume(student)

        student.resume = resume_file
        student.resume_uploaded_at = timezone.now()
        student.save(update_fields=["resume", "resume_uploaded_at"])

        log_audit_event(
            actor=request.user,
            action="RESUME_UPLOADED",
            target_type="Student",
            target_id=student.id,
            description=f"Student {request.user.email} uploaded resume: {resume_file.name}.",
        )

        return Response(
            {
                "message": "Resume uploaded successfully.",
                **_resume_metadata(student),
            },
            status=status.HTTP_201_CREATED,
        )


class StudentResumeDownloadView(APIView):
    """
    GET /students/me/resume/download/

    Returns a JSON body with `download_url` — a Cloudinary URL that carries
    the fl_attachment flag so the browser triggers a file download rather than
    opening the file inline.

    The client should open / redirect to `download_url` directly.
    No server-side redirect is used because Authorization headers are not
    forwarded across cross-origin 302 redirects from API clients.
    """

    permission_classes = [IsAuthenticated, IsStudentUser]

    def get(self, request):
        student = request.user.student_profile

        if not student.resume or not student.resume.name:
            return Response(
                {"error": "No resume uploaded yet."},
                status=status.HTTP_404_NOT_FOUND,
            )

        download_url = _build_download_url(student.resume.name)
        if not download_url:
            return Response(
                {"error": "Resume could not be accessed."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "download_url": download_url,
                "file_name": student.resume.name.split("/")[-1],
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Authorized-staff resume endpoints  (/students/{pk}/resume/...)
# ---------------------------------------------------------------------------


class StaffStudentResumeView(APIView):
    """
    GET /students/{pk}/resume/

    Returns resume metadata for student with Student.id == pk.
    Allowed for: the student, their advisor, their coordinator, a company
    mentor they applied to, or an admin.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        student = get_object_or_404(
            Student.objects.select_related("user", "department", "advisor__user"),
            pk=pk,
        )

        if not _can_access_student_resume(request.user, student):
            raise PermissionDenied(
                "You are not authorized to view this student's resume."
            )

        return Response(_resume_metadata(student), status=status.HTTP_200_OK)


class StaffStudentResumeDownloadView(APIView):
    """
    GET /students/{pk}/resume/download/

    Returns `{download_url, file_name}` for student with Student.id == pk.
    Same authorization rules as StaffStudentResumeView.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        student = get_object_or_404(
            Student.objects.select_related("user", "department", "advisor__user"),
            pk=pk,
        )

        if not _can_access_student_resume(request.user, student):
            raise PermissionDenied(
                "You are not authorized to download this student's resume."
            )

        if not student.resume or not student.resume.name:
            return Response(
                {"error": "This student has not uploaded a resume yet."},
                status=status.HTTP_404_NOT_FOUND,
            )

        download_url = _build_download_url(student.resume.name)
        if not download_url:
            return Response(
                {"error": "Resume could not be accessed."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "download_url": download_url,
                "file_name": student.resume.name.split("/")[-1],
            },
            status=status.HTTP_200_OK,
        )
