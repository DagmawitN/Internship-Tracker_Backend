# core/urls.py
from django.urls import path
from core.views.auth_views import (
    StudentRegisterView,
    CompanyRegisterView,
    LoginView,
    LogoutView,
)
from core.views.admin_views import CompanyApprovalView
from core.views.company_views import CompanyApplicantsListView, CompanyApplicantActionView



urlpatterns = [
    path('auth/student/register/', StudentRegisterView.as_view(), name='student-register'),
    path('auth/company/register/', CompanyRegisterView.as_view(), name='company-register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('admin/company/<int:id>/approve/', CompanyApprovalView.as_view(), name='company-approval'),
    path('company/applicants/', CompanyApplicantsListView.as_view(), name='company-applicants'),
    path('company/applicants/<int:id>/', CompanyApplicantActionView.as_view(), name='company-applicant-action'),
]
