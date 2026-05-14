"""
Dashboard and analytics views.

Views are intentionally thin — all data assembly happens in the service layer.
"""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import (
    IsAdminUser,
    IsAdvisorUser,
    IsCompanyMentor,
    IsCoordinatorUser,
    IsStudentUser,
)
from core.services.analytics_service import (
    get_company_performance,
    get_department_statistics,
    get_placement_analytics,
)
from core.services.dashboard_service import (
    get_admin_dashboard,
    get_advisor_dashboard,
    get_coordinator_dashboard,
    get_mentor_dashboard,
    get_student_dashboard,
)

# ---------------------------------------------------------------------------
# Role-based dashboards
# ---------------------------------------------------------------------------


class StudentDashboardView(APIView):
    """GET /dashboard/student/"""

    permission_classes = [IsAuthenticated, IsStudentUser]

    def get(self, request):
        return Response(get_student_dashboard(request.user))


class AdvisorDashboardView(APIView):
    """GET /dashboard/advisor/"""

    permission_classes = [IsAuthenticated, IsAdvisorUser]

    def get(self, request):
        return Response(get_advisor_dashboard(request.user))


class MentorDashboardView(APIView):
    """GET /dashboard/mentor/"""

    permission_classes = [IsAuthenticated, IsCompanyMentor]

    def get(self, request):
        return Response(get_mentor_dashboard(request.user))


class CoordinatorDashboardView(APIView):
    """GET /dashboard/coordinator/"""

    permission_classes = [IsAuthenticated, IsCoordinatorUser]

    def get(self, request):
        return Response(get_coordinator_dashboard(request.user))


class AdminDashboardView(APIView):
    """GET /dashboard/admin/"""

    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        return Response(get_admin_dashboard())


# ---------------------------------------------------------------------------
# Analytics endpoints
# ---------------------------------------------------------------------------


class PlacementAnalyticsView(APIView):
    """
    GET /analytics/placements/

    Optional query params:
      ?department=<id>
      ?year=<int>
      ?company=<id>
    """

    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        department_id = request.query_params.get("department")
        company_id = request.query_params.get("company")
        year_raw = request.query_params.get("year")

        try:
            year = int(year_raw) if year_raw else None
        except (ValueError, TypeError):
            year = None

        return Response(
            get_placement_analytics(
                department_id=department_id,
                year=year,
                company_id=company_id,
            )
        )


class CompanyPerformanceView(APIView):
    """GET /analytics/company-performance/"""

    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        return Response(get_company_performance())


class DepartmentStatisticsView(APIView):
    """
    GET /analytics/departments/

    Admin   — sees all departments.
    Coordinator — sees only their own department.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        role = getattr(user.role, "role_name", None) if user.role else None

        if role == "ADMIN":
            return Response(get_department_statistics())

        if role == "COORDINATOR":
            staff = getattr(user, "staff", None)
            if staff:
                return Response(
                    get_department_statistics(department_id=staff.department_id)
                )
            return Response({"error": "Coordinator profile not found."}, status=403)

        return Response({"error": "Not authorized."}, status=403)
