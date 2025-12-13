from rest_framework.permissions import BasePermission

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