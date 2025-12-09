from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from core.models import Company, UserRole
from django.contrib.auth import get_user_model

User = get_user_model()

# Custom permission: only Admin can approve companies
from rest_framework.permissions import BasePermission

class IsAdminUser(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.role and request.user.role.role_name == 'ADMIN')


class CompanyApprovalView(generics.UpdateAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = Company.objects.all()
    lookup_field = 'id'

    def patch(self, request, *args, **kwargs):
        company = self.get_object()
        action = request.data.get('action', '').lower()

        if action not in ['approve', 'reject']:
            return Response({'error': 'Action must be "approve" or "reject".'}, status=status.HTTP_400_BAD_REQUEST)

        if action == 'approve':
            company.is_active = True
        else:
            company.is_active = False

        company.save()

        return Response({
            'message': f'Company {action}d successfully',
            'company_id': company.id,
            'is_active': company.is_active
        }, status=status.HTTP_200_OK)
