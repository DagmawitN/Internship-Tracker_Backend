import django_filters
from django.db.models import Q

from core.models import Internship


class InternshipFilter(django_filters.FilterSet):
    """
    FilterSet for the Internship execution model.

    ?student       – searches student_id, first/last name, email (partial, case-insensitive)
    ?company       – searches by numeric company id OR company name substring
    ?status        – exact match (NOT_STARTED | ONGOING | COMPLETED | CANCELLED)
    ?advisor       – exact advisor profile id
    ?department    – exact department id
    ?mentor        – exact CompanyMentor id
    ?start_date    – exact start date
    ?start_date_after  – start_date >= value
    ?start_date_before – start_date <= value
    ?end_date      – exact end date
    ?end_date_after    – end_date >= value
    ?end_date_before   – end_date <= value
    """

    STATUS_CHOICES = [
        ("NOT_STARTED", "Not Started"),
        ("ONGOING", "Ongoing"),
        ("COMPLETED", "Completed"),
        ("CANCELLED", "Cancelled"),
    ]

    student = django_filters.CharFilter(
        method="filter_student", label="Student name or ID"
    )
    company = django_filters.CharFilter(
        method="filter_company", label="Company name or numeric ID"
    )
    status = django_filters.ChoiceFilter(choices=STATUS_CHOICES)
    advisor = django_filters.NumberFilter(
        field_name="student__advisor__id", label="Advisor profile ID"
    )
    department = django_filters.NumberFilter(
        field_name="student__department__id", label="Department ID"
    )
    mentor = django_filters.NumberFilter(
        field_name="mentor__id", label="CompanyMentor ID"
    )

    # Date filters (exact + range)
    start_date = django_filters.DateFilter(field_name="start_date")
    start_date_after = django_filters.DateFilter(
        field_name="start_date", lookup_expr="gte"
    )
    start_date_before = django_filters.DateFilter(
        field_name="start_date", lookup_expr="lte"
    )
    end_date = django_filters.DateFilter(field_name="end_date")
    end_date_after = django_filters.DateFilter(field_name="end_date", lookup_expr="gte")
    end_date_before = django_filters.DateFilter(
        field_name="end_date", lookup_expr="lte"
    )

    class Meta:
        model = Internship
        fields = [
            "status",
            "advisor",
            "department",
            "mentor",
            "start_date",
            "end_date",
        ]

    # ------------------------------------------------------------------
    # Custom filter methods
    # ------------------------------------------------------------------

    def filter_student(self, queryset, name, value):
        """Search student by student_id, first/last name, username, or email."""
        return queryset.filter(
            Q(student__student_id__icontains=value)
            | Q(student__user__first_name__icontains=value)
            | Q(student__user__last_name__icontains=value)
            | Q(student__user__username__icontains=value)
            | Q(student__user__email__icontains=value)
        )

    def filter_company(self, queryset, name, value):
        """Accept either a numeric company id or a company name substring."""
        try:
            company_id = int(value)
            return queryset.filter(
                Q(company__id=company_id) | Q(company__company_name__icontains=value)
            )
        except (ValueError, TypeError):
            return queryset.filter(company__company_name__icontains=value)
