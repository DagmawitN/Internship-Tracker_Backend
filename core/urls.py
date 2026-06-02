# core/urls.py
from django.urls import path

from core.views.admin_views import CompanyApprovalView
from core.views.advisor_views import (
    AdvisorInternshipNotesView,
    AdvisorListView,
    AdvisorMyStudentsView,
    AdvisorReviewView,
    AssignAdvisorView,
    AssignExaminerView,
    ExaminerMyStudentsView,
)
from core.views.staff_views import (
    StaffAssignedListView,
    StaffAssignView,
    StaffUnassignedListView,
    StaffUnassignView,
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
    ExaminerOverallApprovalAPIView,
    ExaminerOverallQueueAPIView,
    FinalIndustryEvaluationDetailAPIView,
    FinalIndustryEvaluationListCreateAPIView,
)
from core.views.export_views import (
    ExportMyAttendanceView,
    ExportMyEvaluationsView,
    ExportMyInternshipsView,
    ExportMyReportsView,
)
from core.views.internship_views import (
    AvailableInternshipPositionListView,
    CancelInternshipView,
    CompleteInternshipView,
    CoordinatorPendingApplicationsListView,
    InternshipApplicationCreateView,
    CoordinatorApprovedApplicationsListView,
    InternshipListCreateView,
    InternshipNotesView,
    InternshipRecordListView,
    InternshipRetrieveUpdateView,
    CompanyUserInternshipListCreateView,
    CompanyUserInternshipRetrieveUpdateView,
    StartInternshipsByPositionView,
    StudentApplicationsListView,
    ApplicationDetailView,
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
    AdvisorInternshipDocumentListAPIView,
    ExaminerInternshipDocumentListAPIView,
    ReportAdvisorReviewAPIView,
    ReportExaminerReviewAPIView,
    StudentInternshipDocumentListCreateAPIView,
    AdvisorWeeklyLogbookListAPIView,
    CompanyWeeklyLogbookListAPIView,
    CreateWeeklyLogbookAPIView,
    ReviewWeeklyLogbookAPIView,
    StudentWeeklyLogbookListAPIView,
    SubmitFinalReportAPIView,
    SubmitWeeklyLogbookAPIView,
    VerifyWeeklyLogbookAPIView,
)
from core.views.resume_views import (
    StaffStudentResumeDownloadView,
    StaffStudentResumeView,
    StudentResumeDownloadView,
    StudentResumeView,
)
from core.views.student_views import AcceptOfferView, StudentCurrentPlacementView
from core.views.student_views import SelfPlacementRequestReviewView, SelfPlacementRequestView
from core.views.user_views import EligibleStudentBulkUploadView, StudentsList, UsersList, UserViewSet
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
    AdvisorExaminerEvaluationsAPIView,
    AdvisorReportApproveAPIView,
    CompanyFinalEvaluationUpsertAPIView,
    CompanyMonthlyEvaluationUpsertAPIView,
    CoordinatorAdvisorEvaluationAPIView,
    CoordinatorOverallApprovalAPIView,
    CoordinatorOverallQueueAPIView,
    ExaminerEvaluationDetailAPIView,
    ExaminerEvaluationListCreateAPIView,
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
    StudentExaminerEvaluationsAPIView,
)
from core.views.user_views import EligibleStudentBulkUploadView, StudentsList, UsersList, UserViewSet



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
    # ------------------------------------------------------------------ Resume (own)
    path(
        "students/me/resume/",
        StudentResumeView.as_view(),
        name="student-resume",
    ),
    path(
        "students/me/resume/download/",
        StudentResumeDownloadView.as_view(),
        name="student-resume-download",
    ),
    # ------------------------------------------------------------------ Resume (authorized staff view)
    path(
        "students/<int:pk>/resume/",
        StaffStudentResumeView.as_view(),
        name="staff-student-resume",
    ),
    path(
        "students/<int:pk>/resume/download/",
        StaffStudentResumeDownloadView.as_view(),
        name="staff-student-resume-download",
    ),
    # ------------------------------------------------------------------ Staff assignment
    path("staff/unassigned/", StaffUnassignedListView.as_view(), name="staff-unassigned"),
    path("staff/assigned/", StaffAssignedListView.as_view(), name="staff-assigned"),
    path("staff/<int:pk>/assign/", StaffAssignView.as_view(), name="staff-assign"),
    path("staff/<int:pk>/unassign/", StaffUnassignView.as_view(), name="staff-unassign"),
    # ------------------------------------------------------------------ Users / students
    path("students/", StudentsList.as_view(), name="student-list"),
    path("users/", UsersList.as_view(), name="users-list"),
    path(
        "eligible-students/",
        EligibleStudentBulkUploadView.as_view(),
        name="eligible-students-list",
    ),
    path(
        "eligible-students/upload/",
        EligibleStudentBulkUploadView.as_view(),
        name="eligible-students-upload",
    ),
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
    path(
        "applications/approved/",
        CoordinatorApprovedApplicationsListView.as_view(),
        name="coordinator-approved-applications",
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
        "internships/<int:user_id>/",
        CompanyUserInternshipListCreateView.as_view(),
        name="internship-list-create-by-user",
    ),
    path(
        "internships/position/<int:position_id>/start/",
        StartInternshipsByPositionView.as_view(),
        name="start-internships-by-position",
    ),
    path(
        "internships/manage/<int:pk>/",
        InternshipRetrieveUpdateView.as_view(),
        name="internship-detail",
    ),
    path(
        "internships/<int:user_id>/detail/<int:pk>/",
        CompanyUserInternshipRetrieveUpdateView.as_view(),
        name="internship-detail-by-user",
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
    # ------------------------------------------------------------------ Student application list
    path(
        "applications/my/",
        StudentApplicationsListView.as_view(),
        name="my-applications",
    ),
    path(
        "applications/",
        CoordinatorPendingApplicationsListView.as_view(),
        name="coordinator-pending-applications",
    ),
    # ------------------------------------------------------------------ Application review workflow
    # Step 1 – Mentor reviews (no coordinator gate required)
    path(
        "applications/<int:pk>/mentor-review/",
        MentorReviewView.as_view(),
        name="mentor-review",
    ),
    path(
        "applications/<int:pk>/",
        ApplicationDetailView.as_view(),
        name="application-detail",
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
    path(
        "students/me/current-placement/",
        StudentCurrentPlacementView.as_view(),
        name="student-current-placement",
    ),
    path(
        "self-placement/request/",
        SelfPlacementRequestView.as_view(),
        name="self-placement-request",
    ),
    path(
        "self-placement/request/<int:pk>/review/",
        SelfPlacementRequestReviewView.as_view(),
        name="self-placement-request-review",
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
    path(
        "students/<int:pk>/assign-examiner/",
        AssignExaminerView.as_view(),
        name="assign-examiner",
    ),
    path(
        "advisor/my-students/",
        AdvisorMyStudentsView.as_view(),
        name="advisor-my-students",
    ),
    path(
        "examiner/my-students/",
        ExaminerMyStudentsView.as_view(),
        name="examiner-my-students",
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
    path('internships/<int:pk>/apply/', InternshipApplicationCreateView.as_view(), name='internship-apply'),
    path('auth/verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('register/staff/', StaffRegisterView.as_view(), name='staff-register'),
    path('me/', MeView.as_view(), name='me'),
    path('logbooks/', CreateWeeklyLogbookAPIView.as_view(), name='logbook-create'),
    path('logbooks/my/', StudentWeeklyLogbookListAPIView.as_view(), name='logbook-my-list'),
    path('logbooks/advisor/', AdvisorWeeklyLogbookListAPIView.as_view(), name='logbook-advisor-list'),
    path('logbooks/company/', CompanyWeeklyLogbookListAPIView.as_view(), name='logbook-company-list'),
    path('documents/my/', StudentInternshipDocumentListCreateAPIView.as_view(), name='student-documents-my'),
    path('documents/advisor/', AdvisorInternshipDocumentListAPIView.as_view(), name='advisor-documents-list'),
    path('documents/examiner/', ExaminerInternshipDocumentListAPIView.as_view(), name='examiner-documents-list'),
    path('documents/<int:pk>/advisor-review/', ReportAdvisorReviewAPIView.as_view(), name='document-advisor-review'),
    path('documents/<int:pk>/examiner-review/', ReportExaminerReviewAPIView.as_view(), name='document-examiner-review'),
    path('documents/<int:pk>/advisor-review/', ReportAdvisorReviewAPIView.as_view(), name='document-advisor-review'),
    path('documents/<int:pk>/examiner-review/', ReportExaminerReviewAPIView.as_view(), name='document-examiner-review'),
    path('logbooks/<int:logbook_id>/entries/', AddDailyLogEntryAPIView.as_view(), name='logbook-add-entry'),
    path('logbooks/<int:logbook_id>/submit/', SubmitWeeklyLogbookAPIView.as_view(), name='logbook-submit'),
    path('logbooks/<int:logbook_id>/verify/', VerifyWeeklyLogbookAPIView.as_view(), name='logbook-verify'),
    path('logbooks/<int:logbook_id>/review/', ReviewWeeklyLogbookAPIView.as_view(), name='logbook-review'),
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
    path(
        "analytics/departments/",
        DepartmentStatisticsView.as_view(),
        name="analytics-departments",
    ),
    # ------------------------------------------------------------------ Exports
    path(
        "exports/my/internships/",
        ExportMyInternshipsView.as_view(),
        name="export-my-internships",
    ),
    path(
        "exports/my/reports/",
        ExportMyReportsView.as_view(),
        name="export-my-reports",
    ),
    path(
        "exports/my/evaluations/",
        ExportMyEvaluationsView.as_view(),
        name="export-my-evaluations",
    ),
    path(
        "exports/my/attendance/",
        ExportMyAttendanceView.as_view(),
        name="export-my-attendance",
    ),
    # ------------------------------------------------------------------ Evaluations
    path(
        "evaluations/final-industry/",
        FinalIndustryEvaluationListCreateAPIView.as_view(),
        name="final-industry-evaluations-list",
    ),
    path(
        "evaluations/final-industry/<int:id>/",
        FinalIndustryEvaluationDetailAPIView.as_view(),
        name="final-industry-evaluation-detail",
    ),
    path(
        "evaluations/advisor/",
        AdvisorEvaluationListCreateAPIView.as_view(),
        name="advisor-evaluations-list",
    ),
    path(
        "evaluations/advisor/for-coordinator/",
        CoordinatorAdvisorEvaluationAPIView.as_view(),
        name="advisor-evaluation-for-coordinator",
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
    # ------------------------------------------------------------------ Examiner evaluations
    path(
        "evaluations/examiner/",
        ExaminerEvaluationListCreateAPIView.as_view(),
        name="examiner-evaluations-list",
    ),
    path(
        "evaluations/examiner/for-advisor/",
        AdvisorExaminerEvaluationsAPIView.as_view(),
        name="examiner-evaluations-for-advisor",
    ),
    path(
        "evaluations/examiner/for-student/",
        StudentExaminerEvaluationsAPIView.as_view(),
        name="examiner-evaluations-for-student",
    ),
    path(
        "evaluations/examiner/<int:pk>/",
        ExaminerEvaluationDetailAPIView.as_view(),
        name="examiner-evaluation-detail",
    ),
    path(
        "evaluations/examiner/<int:internship_id>/overall-approval/",
        ExaminerOverallApprovalAPIView.as_view(),
        name="examiner-overall-approval",
    ),
    path(
        "evaluations/examiner/overall-queue/",
        ExaminerOverallQueueAPIView.as_view(),
        name="examiner-overall-queue",
    ),
    path(
        "evaluations/coordinator/overall-queue/",
        CoordinatorOverallQueueAPIView.as_view(),
        name="coordinator-overall-queue",
    ),
    # ------------------------------------------------------------------ Company evaluations (upsert)
    path(
        "evaluations/company/monthly/",
        CompanyMonthlyEvaluationUpsertAPIView.as_view(),
        name="company-monthly-evaluation",
    ),
    path(
        "evaluations/company/final/",
        CompanyFinalEvaluationUpsertAPIView.as_view(),
        name="company-final-evaluation",
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
