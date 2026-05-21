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
from core.views.dashboard_views import (
    AdminDashboardView,
    AdvisorDashboardView,
    CompanyPerformanceView,
    CoordinatorDashboardView,
    DepartmentStatisticsView,
    MentorDashboardView,
    PlacementAnalyticsView,
    StudentDashboardView,
)
from core.views.department_views import DepartmentViewSet
from core.views.evaluation_views import (
    AdvisorEvaluationDetailAPIView,
    AdvisorEvaluationListCreateAPIView,
    FinalIndustryEvaluationDetailAPIView,
    FinalIndustryEvaluationListCreateAPIView,
)
from core.views.internship_views import (
    AvailableInternshipPositionListView,
    CancelInternshipView,
    CompleteInternshipView,
    InternshipApplicationCreateView,
    InternshipListCreateView,
    InternshipNotesView,
    InternshipRecordListView,
    InternshipRetrieveUpdateView,
    StartInternshipsByPositionView,
)
from core.views.notification_views import (
    MarkAllNotificationsReadView,
    MarkNotificationReadView,
    NotificationListView,
)
from core.views.profile_views import MeView
from core.views.report_views import (
    AddDailyLogEntryAPIView,
    AdvisorFinalReportListAPIView,
    AdvisorWeeklyLogbookListAPIView,
    CreateWeeklyLogbookAPIView,
    SubmitFinalReportAPIView,
)
from core.views.student_views import AcceptOfferView
from core.views.user_views import StudentsList, UsersList, UserViewSet
from core.views.report_views import (
    AddDailyLogEntryAPIView,
    AdvisorFinalReportListAPIView,
    AdvisorWeeklyLogbookListAPIView,
    CreateWeeklyLogbookAPIView,
    SubmitFinalReportAPIView,
)
from core.views.final_report_views import (
    AdvisorFinalReportCommentAPIView,
    ExaminerFinalReportApproveAPIView,
    ExaminerFinalReportDetailAPIView,
    ExaminerFinalReportDownloadAPIView,
    ExaminerFinalReportListAPIView,
    ExaminerFinalReportRejectAPIView,
)
from core.views.evaluation_views import (
    AdvisorApprovalQueueAPIView,
    AdvisorApprovalQueueDetailAPIView,
    AdvisorEvaluationApproveAPIView,
    AdvisorEvaluationDetailAPIView,
    AdvisorEvaluationListCreateAPIView,
    AdvisorEvaluationRejectAPIView,
    AdvisorReportApproveAPIView,
    CoordinatorOverallApprovalAPIView,
    FinalIndustryEvaluationApproveAPIView,
    FinalIndustryEvaluationDetailAPIView,
    FinalIndustryEvaluationListCreateAPIView,
    FinalIndustryEvaluationRejectAPIView,
    MonthlyIndustryEvaluationApproveAPIView,
    MonthlyIndustryEvaluationListCreateAPIView,
    MonthlyIndustryEvaluationRejectAPIView,
    OverallEvaluationDetailAPIView,
    StudentEvaluationStatusAPIView,
    StudentInternshipResultsAPIView,
)



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
    # ------------------------------------------------------------------ Internship records (execution entities – search/filter)
    path(
        "internship-records/",
        InternshipRecordListView.as_view(),
        name="internship-records",
    ),
    # ------------------------------------------------------------------ Internship positions & lifecycle
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
    # Step 1 – Mentor reviews (no coordinator gate required)
    path(
        "applications/<int:pk>/mentor-review/",
        MentorReviewView.as_view(),
        name="mentor-review",
    ),
    # Step 2 – Coordinator assigns advisor via /students/{pk}/assign-advisor/
    # Step 3 – Advisor reviews
    path(
        "applications/<int:pk>/advisor-review/",
        AdvisorReviewView.as_view(),
        name="advisor-review",
    ),
    # Step 4 – Student accepts offer (requires advisor approval)
    path(
        "applications/<int:pk>/accept-offer/",
        AcceptOfferView.as_view(),
        name="accept-offer",
    ),
    # Legacy coordinator dept-review (kept for backward compat)
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
    path('auth/student/register/', StudentRegisterView.as_view(), name='student-register'),
    path('auth/company/register/', CompanyRegisterView.as_view(), name='company-register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('auth/password-reset/request/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('auth/password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('admin/company/<int:id>/approve/', CompanyApprovalView.as_view(), name='company-approval'),
    path('company/<int:company_id>/applicants/', CompanyApplicantsListView.as_view(), name='company-applicants'),
    path('company/<int:company_id>applicants/<int:id>/', CompanyApplicantActionView.as_view(), name='company-applicant-action'),
    path('admin/users/admin-assign-role/',UserViewSet.as_view({'post': 'admin_assign_role'}),name='admin-assign-role'),
    path('admin/users/coordinator-assign-role/',UserViewSet.as_view({'post': 'coordinator_assign_role'}),name='coordinator-assign-role'),
    path('companies/verified/', VerifiedCompaniesListView.as_view(), name='verified-companies'),
    path('students/',StudentsList.as_view(),name='user-list'),
    path('users',UsersList.as_view(),name='users-list'),
    path("internships/", InternshipListCreateView.as_view(), name="internship-list-create"),
    path("internships/<int:pk>/", InternshipRetrieveUpdateView.as_view(), name="internship-detail"),
    path('internships/<int:pk>/apply/', InternshipApplicationCreateView.as_view(), name='internship-apply'),
    path('auth/verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('register/staff/', StaffRegisterView.as_view(), name='staff-register'),
    path('me/', MeView.as_view(), name='me'),
    path('logbooks/', CreateWeeklyLogbookAPIView.as_view()),
    path('logbooks/<int:logbook_id>/entries/', AddDailyLogEntryAPIView.as_view()),
    path("reports/final/<int:student_id>/", SubmitFinalReportAPIView.as_view(), name="submit-final-report"),
    path("advisor/reports/final/", AdvisorFinalReportListAPIView.as_view(), name="advisor-final-reports"),
    path(
        "advisor/final-reports/<int:report_id>/comment/",
        AdvisorFinalReportCommentAPIView.as_view(),
        name="advisor-final-report-comment",
    ),
    path(
        "examiner/final-reports/",
        ExaminerFinalReportListAPIView.as_view(),
        name="examiner-final-reports",
    ),
    path(
        "examiner/final-reports/<int:report_id>/",
        ExaminerFinalReportDetailAPIView.as_view(),
        name="examiner-final-report-detail",
    ),
    path(
        "examiner/final-reports/<int:report_id>/download/",
        ExaminerFinalReportDownloadAPIView.as_view(),
        name="examiner-final-report-download",
    ),
    path(
        "examiner/final-reports/<int:report_id>/approve/",
        ExaminerFinalReportApproveAPIView.as_view(),
        name="examiner-final-report-approve",
    ),
    path(
        "examiner/final-reports/<int:report_id>/reject/",
        ExaminerFinalReportRejectAPIView.as_view(),
        name="examiner-final-report-reject",
    ),
    path("advisor/logbooks/", AdvisorWeeklyLogbookListAPIView.as_view(), name="advisor-weekly-logbooks"),
    path("evaluations/final-industry/", FinalIndustryEvaluationListCreateAPIView.as_view(), name="final-industry-evaluations-list"),
    path("evaluations/final-industry/<int:id>/", FinalIndustryEvaluationDetailAPIView.as_view(), name="final-industry-evaluation-detail"),
    path(
        "evaluations/advisor/",
        AdvisorEvaluationListCreateAPIView.as_view(),
        name="advisor-evaluations-list",
    ),
    path(
        "evaluations/advisor/<int:id>/",
        AdvisorEvaluationDetailAPIView.as_view(),
        name="advisor-evaluation-detail",
    ),
    path(
        "evaluations/advisor/<int:id>/approve/",
        AdvisorEvaluationApproveAPIView.as_view(),
        name="advisor-evaluation-approve",
    ),
    path(
        "evaluations/advisor/<int:id>/reject/",
        AdvisorEvaluationRejectAPIView.as_view(),
        name="advisor-evaluation-reject",
    ),
    path(
        "advisor/approval-queue/",
        AdvisorApprovalQueueAPIView.as_view(),
        name="advisor-approval-queue",
    ),
    path(
        "advisor/approval-queue/<int:internship_id>/",
        AdvisorApprovalQueueDetailAPIView.as_view(),
        name="advisor-approval-queue-detail",
    ),
    path(
        "evaluations/monthly/",
        MonthlyIndustryEvaluationListCreateAPIView.as_view(),
        name="monthly-industry-evaluations",
    ),
    path(
        "evaluations/monthly/<int:id>/approve/",
        MonthlyIndustryEvaluationApproveAPIView.as_view(),
        name="monthly-evaluation-approve",
    ),
    path(
        "evaluations/monthly/<int:id>/reject/",
        MonthlyIndustryEvaluationRejectAPIView.as_view(),
        name="monthly-evaluation-reject",
    ),
    path(
        "evaluations/final-industry/<int:id>/approve/",
        FinalIndustryEvaluationApproveAPIView.as_view(),
        name="final-industry-evaluation-approve",
    ),
    path(
        "evaluations/final-industry/<int:id>/reject/",
        FinalIndustryEvaluationRejectAPIView.as_view(),
        name="final-industry-evaluation-reject",
    ),
    path(
        "reports/<int:report_id>/approve/",
        AdvisorReportApproveAPIView.as_view(),
        name="advisor-report-approve",
    ),
    path(
        "students/evaluation-status/<int:internship_id>/",
        StudentEvaluationStatusAPIView.as_view(),
        name="student-evaluation-status",
    ),
    path(
        "coordinator/overall-evaluation/<int:internship_id>/approve/",
        CoordinatorOverallApprovalAPIView.as_view(),
        name="coordinator-overall-approval",
    ),
    path(
        "overall-evaluation/<int:internship_id>/",
        OverallEvaluationDetailAPIView.as_view(),
        name="overall-evaluation-detail",
    ),
    path(
        "students/internship-results/<int:internship_id>/",
        StudentInternshipResultsAPIView.as_view(),
        name="student-internship-results",
    ),
]
