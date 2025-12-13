# core/urls.py
from django.urls import path
from core.views.auth_views import (
    StudentRegisterView,
    CompanyRegisterView,
    LoginView,
    LogoutView,
)
from core.views.admin_views import CompanyApprovalView
from core.views.company_views import CompanyApplicantsListView, CompanyApplicantActionView , VerifiedCompaniesListView 
from core.views.user_views import UserViewSet
from core.views.internship_views import InternshipApplicationView



urlpatterns = [
    path('auth/student/register/', StudentRegisterView.as_view(), name='student-register'),
    path('auth/company/register/', CompanyRegisterView.as_view(), name='company-register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('admin/company/<int:id>/approve/', CompanyApprovalView.as_view(), name='company-approval'),
    path('company/applicants/', CompanyApplicantsListView.as_view(), name='company-applicants'),
    path('company/applicants/<int:id>/', CompanyApplicantActionView.as_view(), name='company-applicant-action'),
    path('admin/users/assign-role/', UserViewSet.as_view({'post':'action'}), name='assign-role'),
    path('companies/verified/', VerifiedCompaniesListView.as_view(), name='verified-companies'),
    path('companies/<int:company_id>/apply/', InternshipApplicationView.as_view(), name='company-apply'),
]
