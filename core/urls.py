# core/urls.py
from django.urls import path

from core.views.admin_views import CompanyApprovalView
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
from core.views.student_views import AcceptOfferView
from core.views.user_views import StudentsList, UsersList, UserViewSet

urlpatterns = [
    path(
        "auth/student/register/", StudentRegisterView.as_view(), name="student-register"
    ),
    path(
        "auth/company/register/", CompanyRegisterView.as_view(), name="company-register"
    ),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path(
        "admin/company/<int:id>/approve/",
        CompanyApprovalView.as_view(),
        name="company-approval",
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
    path(
        "companies/verified/",
        VerifiedCompaniesListView.as_view(),
        name="verified-companies",
    ),
    path("students/", StudentsList.as_view(), name="user-list"),
    path("users/", UsersList.as_view(), name="users-list"),
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
        "internships/<int:pk>/apply/",
        InternshipApplicationCreateView.as_view(),
        name="internship-apply",
    ),
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
    path("register/staff/", StaffRegisterView.as_view(), name="staff-register"),
    path("me/", MeView.as_view(), name="me"),
    # reviews of internship application before acceptance
    path("applications/<int:pk>/dept-review/", DepartmentReviewView.as_view()),
    path("applications/<int:pk>/mentor-review/", MentorReviewView.as_view()),
    path("applications/<int:pk>/accept-offer/", AcceptOfferView.as_view()),
]
