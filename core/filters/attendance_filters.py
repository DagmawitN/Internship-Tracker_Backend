import django_filters
from django.db.models import Q

from core.models import Attendance


class AttendanceFilter(django_filters.FilterSet):
    """
    FilterSet for Attendance records.

    ?internship           – exact Internship id
    ?student              – student_id, name, or email substring
    ?status               – PRESENT | LATE | ABSENT
    ?date                 – exact date
    ?start_date           – date >= value
    ?end_date             – date <= value
    ?is_location_verified – true | false
    ?company              – numeric company id OR company name substring
    ?department           – exact department id
    """

    STATUS_CHOICES = [
        ("PRESENT", "Present"),
        ("LATE", "Late"),
        ("ABSENT", "Absent"),
    ]

    internship = django_filters.NumberFilter(
        field_name="internship__id", label="Internship ID"
    )
    student = django_filters.CharFilter(
        method="filter_student", label="Student name, ID, or email"
    )
    status = django_filters.ChoiceFilter(choices=STATUS_CHOICES)
    date = django_filters.DateFilter(field_name="date")
    start_date = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    end_date = django_filters.DateFilter(field_name="date", lookup_expr="lte")
    is_location_verified = django_filters.BooleanFilter(
        field_name="is_location_verified"
    )
    company = django_filters.CharFilter(
        method="filter_company", label="Company name or numeric ID"
    )
    department = django_filters.NumberFilter(
        field_name="internship__student__department__id", label="Department ID"
    )

    class Meta:
        model = Attendance
        fields = [
            "internship",
            "status",
            "date",
            "is_location_verified",
            "department",
        ]

    # ------------------------------------------------------------------
    # Custom filter methods
    # ------------------------------------------------------------------

    def filter_student(self, queryset, name, value):
        return queryset.filter(
            Q(internship__student__student_id__icontains=value)
            | Q(internship__student__user__first_name__icontains=value)
            | Q(internship__student__user__last_name__icontains=value)
            | Q(internship__student__user__username__icontains=value)
            | Q(internship__student__user__email__icontains=value)
        )

    def filter_company(self, queryset, name, value):
        try:
            company_id = int(value)
            return queryset.filter(
                Q(internship__company__id=company_id)
                | Q(internship__company__company_name__icontains=value)
            )
        except (ValueError, TypeError):
            return queryset.filter(internship__company__company_name__icontains=value)
