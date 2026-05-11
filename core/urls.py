# core/urls.py
from django.urls import path

from core.views.admin_views import CompanyApprovalView
from core.views.advisor_views import (
    AdvisorInternshipNotesView,
    AdvisorListView,
    AdvisorReviewView,
    AssignAdvisorView,
)
from core.views.attendance_views import (
    AttendanceDetailView,
    AttendanceListView,
    AttendanceNotesUpdateView,
    CheckInView,
    CheckOutView,
)
from core.views.auth_views import (
    CompanyRegisterView,
    LoginView,
    LogoutView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    ResendOTPView,
    StaffRegisterView,
    StudentRegisterView,
    VerifyOTPView,
)
from core.views.company_views import (
    CompanyApplicantActionView,
    CompanyApplicantsListView,
    MentorReviewView,
    VerifiedCompaniesListView,
)
from core.views.coordinator_views import DepartmentReviewView
from core.views.department_views import DepartmentViewSet
from core.views.internship_views import *
from core.views.profile_views import MeView
from core.views.report_views import (
    AddDailyLogEntryAPIView,
    CreateWeeklyLogbookAPIView,
    SubmitFinalReportAPIView,
)
from core.views.student_views import AcceptOfferView
from core.views.user_views import StudentsList, UsersList, UserViewSet

urlpatterns = [
    # ------------------------------------------------------------------ Auth
    path(
        "auth/student/register/", StudentRegisterView.as_view(), name="student-register"
    ),
    path(
        "auth/company/register/", CompanyRegisterView.as_view(), name="company-register"
    ),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/verify-otp/", VerifyOTPView.as_view(), name="verify-otp"),
    path("auth/resend-otp/", ResendOTPView.as_view(), name="resend-otp"),
    path(
        "auth/password-reset/",
        PasswordResetRequestView.as_view(),
        name="password-reset-request",
    ),
    path(
        "auth/password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    path("register/staff/", StaffRegisterView.as_view(), name="staff-register"),
    # ------------------------------------------------------------------ Profile
    path("me/", MeView.as_view(), name="me"),
    # ------------------------------------------------------------------ Users / students
    path("students/", StudentsList.as_view(), name="student-list"),
    path("users/", UsersList.as_view(), name="users-list"),
    # ------------------------------------------------------------------ Admin
    path(
        "admin/company/<int:id>/approve/",
        CompanyApprovalView.as_view(),
        name="company-approval",
    ),
    path(
        "admin/users/admin-assign-role/",
        UserViewSet.as_view({"post": "admin_assign_role"}),
        name="admin-assign-role",
    ),
    path(
        "admin/users/coordinator-assign-role/",
        UserViewSet.as_view({"post": "coordinator_assign_role"}),
        name="coordinator-assign-role",
    ),
    # ------------------------------------------------------------------ Departments
    path(
        "departments/",
        DepartmentViewSet.as_view({"get": "list", "post": "create"}),
        name="department-list",
    ),
    path(
        "departments/<int:pk>/",
        DepartmentViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="department-detail",
    ),
    # ------------------------------------------------------------------ Companies
    path(
        "companies/verified/",
        VerifiedCompaniesListView.as_view(),
        name="verified-companies",
    ),
    path(
        "company/<int:company_id>/applicants/",
        CompanyApplicantsListView.as_view(),
        name="company-applicants",
    ),
    path(
        "company/<int:company_id>/applicants/<int:id>/",
        CompanyApplicantActionView.as_view(),
        name="company-applicant-action",
    ),
    # ------------------------------------------------------------------ Internship positions
    path(
        "internship-positions/",
        AvailableInternshipPositionListView.as_view(),
        name="available-internship-positions",
    ),
    path(
        "internships/",
        InternshipListCreateView.as_view(),
        name="internship-list-create",
    ),
    path(
        "internships/position/<int:position_id>/start/",
        StartInternshipsByPositionView.as_view(),
        name="start-internships-by-position",
    ),
    path(
        "internships/<int:pk>/",
        InternshipRetrieveUpdateView.as_view(),
        name="internship-detail",
    ),
    path(
        "internships/<int:pk>/apply/",
        InternshipApplicationCreateView.as_view(),
        name="internship-apply",
    ),
    path(
        "internships/<int:pk>/complete/",
        CompleteInternshipView.as_view(),
        name="internship-complete",
    ),
    path(
        "internships/<int:pk>/cancel/",
        CancelInternshipView.as_view(),
        name="internship-cancel",
    ),
    path(
        "internships/<int:pk>/notes/",
        InternshipNotesView.as_view(),
        name="internship-notes",
    ),
    path(
        "internships/<int:pk>/advisor-notes/",
        AdvisorInternshipNotesView.as_view(),
        name="advisor-internship-notes",
    ),
    # ------------------------------------------------------------------ Application review workflow
    path(
        "applications/<int:pk>/mentor-review/",
        MentorReviewView.as_view(),
        name="mentor-review",
    ),
    path(
        "applications/<int:pk>/advisor-review/",
        AdvisorReviewView.as_view(),
        name="advisor-review",
    ),
    path(
        "applications/<int:pk>/accept-offer/",
        AcceptOfferView.as_view(),
        name="accept-offer",
    ),
    path(
        "applications/<int:pk>/dept-review/",
        DepartmentReviewView.as_view(),
        name="dept-review",
    ),
    # ------------------------------------------------------------------ Advisor management
    path("advisors/", AdvisorListView.as_view(), name="advisor-list"),
    path(
        "students/<int:pk>/assign-advisor/",
        AssignAdvisorView.as_view(),
        name="assign-advisor",
    ),
    # ------------------------------------------------------------------ Attendance
    path("attendance/check-in/", CheckInView.as_view(), name="attendance-check-in"),
    path("attendance/check-out/", CheckOutView.as_view(), name="attendance-check-out"),
    path("attendance/", AttendanceListView.as_view(), name="attendance-list"),
    path(
        "attendance/<int:pk>/", AttendanceDetailView.as_view(), name="attendance-detail"
    ),
    path(
        "attendance/<int:pk>/notes/",
        AttendanceNotesUpdateView.as_view(),
        name="attendance-notes",
    ),
    # ------------------------------------------------------------------ Logbooks / reports
    path("logbooks/", CreateWeeklyLogbookAPIView.as_view()),
    path("logbooks/<int:logbook_id>/entries/", AddDailyLogEntryAPIView.as_view()),
    path(
        "reports/final/<int:student_id>/",
        SubmitFinalReportAPIView.as_view(),
        name="submit-final-report",
    ),
]
