from rest_framework.permissions import BasePermission
from .models import CompanyMentor

# Custom permission to allow only admin users
class IsAdminUser(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.role and request.user.is_authenticated and request.user.role.role_name == 'ADMIN')

# Custom permission to allow only coordinators
class IsCoordinatorUser(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.role and request.user.is_authenticated and request.user.role.role_name == 'COORDINATOR')
# Custom permission to allow only Students
class IsStudentUser(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.role and request.user.is_authenticated and request.user.role.role_name == 'STUDENT')
    
class IsCompanyMentor(BasePermission):
   
    def has_permission(self, request, view):
        return CompanyMentor.objects.filter(user=request.user).exists()


class IsMentorOfCompany(BasePermission):
    def has_object_permission(self, request, view, obj):
        if obj is None:
            return True
        return CompanyMentor.objects.filter(
            user=request.user,
            company=obj.company
        ).exists()