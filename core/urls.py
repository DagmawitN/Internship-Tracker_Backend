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
from core.views.user_views import UserViewSet, StudentsList,UsersList
from core.views.internship_views import *



urlpatterns = [
    path('auth/student/register/', StudentRegisterView.as_view(), name='student-register'),
    path('auth/company/register/', CompanyRegisterView.as_view(), name='company-register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
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
    path('internships/<int:pk>/apply/', InternshipApplicationCreateView.as_view(), name='internship-apply')

]
