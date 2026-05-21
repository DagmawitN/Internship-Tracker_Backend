import random

from cloudinary.models import CloudinaryField
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .custom_manager import CustomUserManager


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UserRole(models.Model):
    role_name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.role_name


class User(AbstractUser):
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)

    role = models.ForeignKey(UserRole, on_delete=models.PROTECT, null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)

    last_login = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = CustomUserManager()

    def __str__(self):
        return self.username or self.email


class EmailOTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return timezone.now() > self.created_at + timezone.timedelta(minutes=10)

    @staticmethod
    def generate_otp():
        return str(random.randint(100000, 999999))


class Admin(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="admin_profile"
    )
    admin_level = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"Admin: {self.user}"


class Department(TimeStampedModel):
    department_code = models.CharField(max_length=20)
    department_name = models.CharField(max_length=100, unique=True)
    college = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.department_name


class Company(TimeStampedModel):
    company_name = models.CharField(max_length=150)
    registration_number = models.CharField(max_length=50, blank=True)
    industry_type = models.CharField(max_length=100, blank=True)
    address = models.CharField(max_length=200, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    website = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.company_name


class CompanyMentor(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="company_mentorships",
    )
    company = models.OneToOneField(
        Company, on_delete=models.CASCADE, related_name="mentor"
    )
    position = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.user} - {self.company}"


class Supervisor(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="supervisions"
    )
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True
    )
    supervisor_type = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"Supervisor: {self.user}"


class Advisor(TimeStampedModel):
    """Departmental academic advisor who supervises assigned students' internships."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="advisor_profile",
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="advisors",
    )

    def __str__(self):
        return f"Advisor: {self.user}"


class Student(TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_profile",
    )
    student_id = models.CharField(max_length=20)
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="students"
    )
    advisor = models.ForeignKey(
        "Advisor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_students",
    )

    def __str__(self):
        return f"{self.student_id} - {self.user}"


class Skill(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class InternshipPosition(TimeStampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="internship_positions",
        db_index=True,
    )

    title = models.CharField(blank=False, max_length=200)
    description = models.TextField()

    required_skills = models.ManyToManyField(
        Skill, related_name="internship_positions", blank=True
    )

    duration_weeks = models.PositiveIntegerField(null=True, blank=True)
    application_deadline = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    max_applicants = models.PositiveIntegerField(null=True, blank=True)

    # Schedule
    working_days = models.JSONField(
        default=list,
        blank=True,
        help_text='List of weekday names, e.g. ["MONDAY","TUESDAY","WEDNESDAY","THURSDAY","FRIDAY"]',
    )
    daily_start_time = models.TimeField(null=True, blank=True)
    daily_end_time = models.TimeField(null=True, blank=True)

    # Location
    is_remote = models.BooleanField(default=False)
    work_latitude = models.FloatField(null=True, blank=True)
    work_longitude = models.FloatField(null=True, blank=True)
    allowed_radius_meters = models.PositiveIntegerField(default=200)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company", "is_active"]),
            models.Index(fields=["application_deadline"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.company.company_name}"


class InternshipApplication(TimeStampedModel):
    class DeptStatus(models.TextChoices):
        PENDING = "PENDING"
        APPROVED = "APPROVED"
        REJECTED = "REJECTED"

    class MentorStatus(models.TextChoices):
        PENDING = "PENDING"
        ACCEPTED = "ACCEPTED"  # offer
        REJECTED = "REJECTED"

    class StudentDecision(models.TextChoices):
        PENDING = "PENDING"
        ACCEPTED = "ACCEPTED"
        DECLINED = "DECLINED"

    class AdvisorStatus(models.TextChoices):
        PENDING = "PENDING"
        APPROVED = "APPROVED"
        REJECTED = "REJECTED"

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="applications"
    )
    position = models.ForeignKey(
        InternshipPosition, on_delete=models.CASCADE, related_name="applications"
    )
    supervisor = models.ForeignKey(
        Supervisor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applications",
    )
    mentor = models.ForeignKey(
        CompanyMentor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applications",
    )
    dept_status = models.CharField(
        max_length=20, choices=DeptStatus.choices, default=DeptStatus.PENDING
    )

    mentor_status = models.CharField(
        max_length=20, choices=MentorStatus.choices, null=True, blank=True
    )

    student_decision = models.CharField(
        max_length=20, choices=StudentDecision.choices, default=StudentDecision.PENDING
    )

    # Advisor review (new workflow)
    advisor = models.ForeignKey(
        "Advisor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_applications",
    )
    advisor_status = models.CharField(
        max_length=20,
        choices=AdvisorStatus.choices,
        default=AdvisorStatus.PENDING,
    )
    advisor_notes = models.TextField(blank=True)

    class Meta:
        unique_together = ("student", "position")

    def __str__(self):
        return f"{self.student} -> {self.position.title} ({self.dept_status})"


class Internship(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    position = models.ForeignKey(InternshipPosition, on_delete=models.CASCADE)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="internships",
        null=True,
        blank=True,
    )
    supervisor = models.ForeignKey(
        Supervisor, on_delete=models.SET_NULL, null=True, blank=True
    )
    mentor = models.ForeignKey(
        CompanyMentor, on_delete=models.SET_NULL, null=True, blank=True
    )

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=[
            ("NOT_STARTED", "Not Started"),
            ("ONGOING", "Ongoing"),
            ("COMPLETED", "Completed"),
            ("CANCELLED", "Cancelled"),
        ],
        default="NOT_STARTED",
    )
    total_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    notes = models.TextField(blank=True)


class Attendance(TimeStampedModel):
    class Status(models.TextChoices):
        PRESENT = "PRESENT", "Present"
        LATE = "LATE", "Late"
        ABSENT = "ABSENT", "Absent"

    internship = models.ForeignKey(
        Internship, on_delete=models.CASCADE, related_name="attendances"
    )
    date = models.DateField()
    check_in_time = models.TimeField(null=True, blank=True)
    check_out_time = models.TimeField(null=True, blank=True)
    total_hours = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PRESENT
    )
    notes = models.TextField(blank=True)

    # GPS (captured at check-in)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    accuracy = models.FloatField(null=True, blank=True)
    is_location_verified = models.BooleanField(default=False)

    class Meta:
        unique_together = ("internship", "date")

    def __str__(self):
        return f"Attendance {self.id} - {self.internship} - {self.date}"


class AttendanceLocation(TimeStampedModel):
    attendance = models.ForeignKey(
        Attendance, on_delete=models.CASCADE, related_name="locations"
    )
    latitude = models.DecimalField(max_digits=10, decimal_places=8)
    longitude = models.DecimalField(max_digits=11, decimal_places=8)
    accuracy = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    recorded_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Location for {self.attendance}"


class ReportReviewStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    SUBMITTED = "SUBMITTED", "Submitted by Student"
    EXAMINER_APPROVED = "EXAMINER_APPROVED", "Approved by Examiner"
    EXAMINER_REJECTED = "EXAMINER_REJECTED", "Rejected by Examiner"
    ADVISOR_APPROVED = "ADVISOR_APPROVED", "Approved by Advisor"
    REJECTED = "REJECTED", "Rejected"


class Report(TimeStampedModel):
    REPORT_TYPES = [
        ("WEEKLY", "Weekly"),
        ("MONTHLY", "Monthly"),
        ("FINAL", "Final"),
        ("OTHER", "Other"),
    ]

    internship = models.ForeignKey(
        InternshipApplication, on_delete=models.CASCADE, related_name="reports"
    )
    week_number = models.IntegerField(null=True, blank=True)
    submission_date = models.DateTimeField(null=True, blank=True)
    report_type = models.CharField(
        max_length=30, choices=REPORT_TYPES, default="WEEKLY"
    )
    title = models.CharField(max_length=200, blank=True)
    status = models.CharField(
        max_length=30,
        choices=ReportReviewStatus.choices,
        blank=True,
        default=ReportReviewStatus.SUBMITTED,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_reports",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    examiner_reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="examiner_reviewed_reports",
    )
    examiner_approved_at = models.DateTimeField(null=True, blank=True)
    examiner_rejected_at = models.DateTimeField(null=True, blank=True)
    advisor_comment = models.TextField(blank=True)
    advisor_comment_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="advisor_commented_reports",
    )
    advisor_comment_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Report {self.id} - {self.internship}"


class ReportFile(TimeStampedModel):
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name="files")
    file_name = models.CharField(max_length=200)
    file = models.FileField(upload_to="final_reports/", null=True, blank=True)
    file_size = models.BigIntegerField(null=True, blank=True)
    mime_type = models.CharField(max_length=100, blank=True)
    uploaded_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.file_name


class ReportFeedback(TimeStampedModel):
    report = models.ForeignKey(
        Report, on_delete=models.CASCADE, related_name="feedbacks"
    )
    supervisor = models.ForeignKey(
        Supervisor, on_delete=models.SET_NULL, null=True, blank=True
    )
    feedback_text = models.TextField(blank=True)

    def __str__(self):
        return f"Feedback {self.id} on {self.report}"


class Evaluation(TimeStampedModel):
    EVAL_TYPES = [
        ("MIDTERM", "Midterm"),
        ("FINAL", "Final"),
        ("OTHER", "Other"),
    ]

    internship = models.ForeignKey(
        InternshipApplication, on_delete=models.CASCADE, related_name="evaluations"
    )
    supervisor = models.ForeignKey(
        Supervisor, on_delete=models.SET_NULL, null=True, blank=True
    )
    evaluation_type = models.CharField(
        max_length=30, choices=EVAL_TYPES, default="FINAL"
    )
    technical_skills_score = models.DecimalField(
        max_digits=5, decimal_places=3, null=True, blank=True
    )
    communication_score = models.DecimalField(
        max_digits=5, decimal_places=3, null=True, blank=True
    )
    professionalism_score = models.DecimalField(
        max_digits=5, decimal_places=3, null=True, blank=True
    )
    problem_solving_score = models.DecimalField(
        max_digits=5, decimal_places=3, null=True, blank=True
    )
    overall_score = models.DecimalField(
        max_digits=5, decimal_places=3, null=True, blank=True
    )
    general_feedback = models.TextField(blank=True)
    strengths = models.TextField(blank=True)
    areas_for_improvement = models.TextField(blank=True)
    evaluation_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"Evaluation {self.id} - {self.internship}"


class AdvisorAssignment(TimeStampedModel):
    coordinator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="coordinator_assignments",
    )
    advisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="advisor_assignments",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="advisor_for_student",
    )
    internship = models.ForeignKey(
        InternshipApplication,
        on_delete=models.CASCADE,
        related_name="advisor_assignments",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    role = models.CharField(
        max_length=30,
        choices=[("ADVISOR", "Advisor"), ("EXAMINER", "Examiner")],
        default="ADVISOR",
    )

    class Meta:
        unique_together = ("advisor", "internship")

    def __str__(self):
        return f"{self.role} {self.advisor} assigned to {self.student} for {self.internship}"


class AdvisorEvaluation(TimeStampedModel):
    """
    AASTU VPAA/DPT/OF/003 — University Supervisor Internship Evaluation Form.
    Contributes 35% (Report 20%, Logbook 5%, Performance 10%) to the overall result.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    internship = models.OneToOneField(
        InternshipApplication,
        on_delete=models.CASCADE,
        related_name="advisor_evaluation",
        related_name="advisor_evaluation",
    )
    advisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_advisor_evaluations",
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    # Section 1 — Report Evaluation (20%)
    report_format_score = models.PositiveIntegerField(default=0)
    organization_background_score = models.PositiveIntegerField(default=0)
    activities_score = models.PositiveIntegerField(default=0)
    data_figure_table_score = models.PositiveIntegerField(default=0)
    report_content_score = models.PositiveIntegerField(default=0)
    recommendation_score = models.PositiveIntegerField(default=0)
    conclusion_score = models.PositiveIntegerField(default=0)
    report_total = models.PositiveIntegerField(default=0)
    weighted_report_mark = models.DecimalField(max_digits=5, decimal_places=3, default=0)

    # Section 2 — Logbook Evaluation (5%)
    pictures_and_data_score = models.PositiveIntegerField(default=0)
    weekly_summary_score = models.PositiveIntegerField(default=0)
    daily_detail_score = models.PositiveIntegerField(default=0)
    improvement_score = models.PositiveIntegerField(default=0)
    initiative_score = models.PositiveIntegerField(default=0)
    logbook_total = models.PositiveIntegerField(default=0)
    weighted_logbook_mark = models.DecimalField(max_digits=5, decimal_places=3, default=0)

    # Section 3 — Student Performance (10%)
    understanding_objective_score = models.PositiveIntegerField(default=0)
    engagement_score = models.PositiveIntegerField(default=0)
    discipline_score = models.PositiveIntegerField(default=0)
    student_performance_total = models.PositiveIntegerField(default=0)
    weighted_student_performance_mark = models.DecimalField(
        max_digits=5, decimal_places=3, default=0
    )

    # Final calculations
    total_marks = models.PositiveIntegerField(default=0)
    final_weighted_mark = models.DecimalField(max_digits=5, decimal_places=3, default=0)

    class Meta:
        verbose_name = "Advisor Evaluation"
        verbose_name_plural = "Advisor Evaluations"
        constraints = [
            models.UniqueConstraint(
                fields=["internship"],
                name="unique_advisor_evaluation_per_internship",
            ),
        ]

    def calculate_scores(self):
        from core.evaluation_constants import (
            LOGBOOK_SCORE_FIELDS,
            PERFORMANCE_SCORE_FIELDS,
            REPORT_SCORE_FIELDS,
        )

        self.report_total = sum(
            getattr(self, field) for field in REPORT_SCORE_FIELDS
        )
        self.logbook_total = sum(
            getattr(self, field) for field in LOGBOOK_SCORE_FIELDS
        )
        self.student_performance_total = sum(
            getattr(self, field) for field in PERFORMANCE_SCORE_FIELDS
        )
        self.weighted_report_mark = self.report_total
        self.weighted_logbook_mark = self.logbook_total
        self.weighted_student_performance_mark = self.student_performance_total
        self.total_marks = (
            self.report_total + self.logbook_total + self.student_performance_total
        )
        self.final_weighted_mark = (
            self.weighted_report_mark
            + self.weighted_logbook_mark
            + self.weighted_student_performance_mark
        )

    def clean(self):
        from django.core.exceptions import ValidationError

        from core.evaluation_validators import validate_advisor_score_fields

        validate_advisor_score_fields(self)

        if AdvisorEvaluation.objects.filter(internship=self.internship).exclude(
            pk=self.pk
        ).exists():
            raise ValidationError(
                {"internship": "An advisor evaluation already exists for this internship."}
            )

    def save(self, *args, **kwargs):
        self.calculate_scores()
        super().save(*args, **kwargs)
        from core.services.evaluation_workflow import sync_overall_from_advisor

        sync_overall_from_advisor(self)

    def __str__(self):
        return f"Advisor Evaluation - {self.internship.student} ({self.status})"


class ExaminerEvaluation(TimeStampedModel):
    """Examiner panel evaluation; two slots contribute up to 45% combined."""

    internship = models.ForeignKey(
        InternshipApplication,
        on_delete=models.CASCADE,
        related_name="examiner_evaluations",
    )
    examiner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_examiner_evaluations",
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    technical_skills_score = models.PositiveIntegerField(default=0)
    communication_score = models.PositiveIntegerField(default=0)
    professionalism_score = models.PositiveIntegerField(default=0)
    report_quality_score = models.PositiveIntegerField(default=0)
    presentation_score = models.PositiveIntegerField(default=0)
    comments = models.TextField(blank=True)
    total_score = models.PositiveIntegerField(default=0)
    weighted_score = models.DecimalField(max_digits=5, decimal_places=3, default=0)

    class Meta:
        verbose_name = "Examiner Evaluation"
        verbose_name_plural = "Examiner Evaluations"
        constraints = [
            models.UniqueConstraint(
                fields=["internship", "examiner"],
                name="unique_examiner_evaluation",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    technical_skills_score__gte=0,
                    technical_skills_score__lte=5,
                    communication_score__gte=0,
                    communication_score__lte=5,
                    professionalism_score__gte=0,
                    professionalism_score__lte=5,
                    report_quality_score__gte=0,
                    report_quality_score__lte=5,
                    presentation_score__gte=0,
                    presentation_score__lte=5,
                ),
                name="examiner_eval_scores_range",
            ),
        ]

    def calculate_scores(self):
        from core.evaluation_constants import EXAMINER_RAW_MAX, EXAMINER_WEIGHTED_MAX

        self.total_score = (
            self.technical_skills_score
            + self.communication_score
            + self.professionalism_score
            + self.report_quality_score
            + self.presentation_score
        )
        if self.total_score > 0:
            self.weighted_score = (self.total_score / EXAMINER_RAW_MAX) * EXAMINER_WEIGHTED_MAX
        else:
            self.weighted_score = 0


    def save(self, *args, **kwargs):
        self.calculate_scores()
        super().save(*args, **kwargs)
        from core.services.evaluation_workflow import sync_overall_from_examiner

        sync_overall_from_examiner(self.internship_id)


class OverallInternshipEvaluation(TimeStampedModel):
    """Aggregated internship result across advisor, examiners, and company."""

    class Status(models.TextChoices):
        PENDING_ADVISOR = "PENDING_ADVISOR", "Pending Advisor"
        PENDING_EXAMINERS = "PENDING_EXAMINERS", "Pending Examiners"
        PENDING_COORDINATOR = "PENDING_COORDINATOR", "Pending Coordinator"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    internship = models.OneToOneField(
        InternshipApplication,
        on_delete=models.CASCADE,
        related_name="overall_evaluation",
    )
    advisor_evaluation = models.OneToOneField(
        AdvisorEvaluation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    company_evaluation = models.OneToOneField(
        "FinalIndustryEvaluation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    examiner_one_evaluation = models.OneToOneField(
        ExaminerEvaluation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="overall_eval_one",
    )
    examiner_two_evaluation = models.OneToOneField(
        ExaminerEvaluation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="overall_eval_two",
    )
    advisor_score = models.DecimalField(
        max_digits=5, decimal_places=3, null=True, blank=True
    )
    examiner_average_score = models.DecimalField(
        max_digits=5, decimal_places=3, null=True, blank=True
    )
    company_score = models.DecimalField(
        max_digits=5, decimal_places=3, null=True, blank=True
    )
    final_total_score = models.DecimalField(
        max_digits=5, decimal_places=3, null=True, blank=True
    )
    final_grade = models.CharField(max_length=5, blank=True)
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING_ADVISOR,
    )
    advisor_approved = models.BooleanField(default=False)
    examiner_completed = models.BooleanField(default=False)
    coordinator_approved = models.BooleanField(default=False)
    advisor_approved_at = models.DateTimeField(null=True, blank=True)
    examiner_completed_at = models.DateTimeField(null=True, blank=True)
    coordinator_approved_at = models.DateTimeField(null=True, blank=True)
    coordinator_comment = models.TextField(blank=True)
    visible_to_student = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_overall_evals",
    )

    def calculate_final(self):
        """Aggregate component scores into final_total_score and grade."""
        from decimal import Decimal

        from core.services.evaluation_workflow import compute_final_grade

        advisor = Decimal(str(self.advisor_score or 0))
        company = Decimal(str(self.company_score or 0))
        examiner_total = Decimal("0")
        if self.examiner_one_evaluation_id:
            examiner_total += Decimal(
                str(self.examiner_one_evaluation.weighted_score or 0)
            )
        if self.examiner_two_evaluation_id:
            examiner_total += Decimal(
                str(self.examiner_two_evaluation.weighted_score or 0)
            )
        self.examiner_average_score = examiner_total
        self.final_total_score = advisor + company + examiner_total
        self.final_grade = compute_final_grade(self.final_total_score)

    def save(self, *args, **kwargs):
        if self.advisor_score is not None or self.company_score is not None:
            self.calculate_final()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Overall Evaluation - {self.internship_id} ({self.status})"


class PreRegisteredStudent(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    student_id = models.CharField(max_length=12, unique=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    is_used = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name}({self.student_id})"


class PreRegisteredStaff(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=50, blank=True)
    is_used = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name}"


class Staff(TimeStampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.name} ({self.user.email})"


# model for user profiles
class Profile(TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )

    bio = models.TextField(blank=True)
    avatar = CloudinaryField("image", blank=True, null=True)
    location = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"Profile - {self.user}"


class WeeklyLogbook(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted"
        VERIFIED = "VERIFIED", "Verified"
        REVIEWED = "REVIEWED", "Reviewed"

    internship = models.ForeignKey(
        InternshipApplication, on_delete=models.CASCADE, related_name="weekly_logbooks"
    )

    week_number = models.PositiveIntegerField()

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )

    student_comment = models.TextField(blank=True)

    company_comment = models.TextField(blank=True)

    advisor_comment = models.TextField(blank=True)

    verified_by = models.ForeignKey(
        CompanyMentor, on_delete=models.SET_NULL, null=True, blank=True
    )

    reviewed_by = models.ForeignKey(
        Supervisor, on_delete=models.SET_NULL, null=True, blank=True
    )

    submitted_at = models.DateTimeField(null=True, blank=True)

    verified_at = models.DateTimeField(null=True, blank=True)

    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["internship", "week_number"], name="unique_weekly_logbook"
            )
        ]


class DailyLogEntry(TimeStampedModel):
    weekly_logbook = models.ForeignKey(
        WeeklyLogbook, on_delete=models.CASCADE, related_name="daily_entries"
    )

    day_number = models.PositiveIntegerField()

    work_date = models.DateField()

    work_performed = models.TextField()


class CompanyEvaluationStatus(models.TextChoices):
    """Shared workflow for company-submitted monthly and final evaluations."""

    PENDING = "PENDING", "Pending"
    SUBMITTED = "SUBMITTED", "Submitted by Company"
    ADVISOR_APPROVED = "ADVISOR_APPROVED", "Approved by Advisor"
    REJECTED = "REJECTED", "Rejected"


class MonthlyIndustryEvaluation(TimeStampedModel):
    """Monthly industry supervisor evaluation submitted by company mentor."""

    internship = models.ForeignKey(
        InternshipApplication,
        on_delete=models.CASCADE,
        related_name="monthly_industry_evaluations",
    )
    month_number = models.PositiveIntegerField()
    company_mentor = models.ForeignKey(
        CompanyMentor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="monthly_evaluations",
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=CompanyEvaluationStatus.choices,
        default=CompanyEvaluationStatus.SUBMITTED,
    )
    advisor_reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_monthly_evaluations",
    )
    advisor_approved_at = models.DateTimeField(null=True, blank=True)
    advisor_rejected_at = models.DateTimeField(null=True, blank=True)
    visible_to_student = models.BooleanField(default=False)

    work_quality_score = models.PositiveIntegerField(default=0)
    punctuality_score = models.PositiveIntegerField(default=0)
    attitude_score = models.PositiveIntegerField(default=0)
    initiative_score = models.PositiveIntegerField(default=0)
    comments = models.TextField(blank=True)
    total_score = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Monthly Industry Evaluation"
        verbose_name_plural = "Monthly Industry Evaluations"
        constraints = [
            models.UniqueConstraint(
                fields=["internship", "month_number"],
                name="unique_monthly_eval_per_internship_month",
            ),
        ]

    def calculate_totals(self):
        self.total_score = (
            self.work_quality_score
            + self.punctuality_score
            + self.attitude_score
            + self.initiative_score
        )

    def save(self, *args, **kwargs):
        self.calculate_totals()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Monthly Eval M{self.month_number} - {self.internship_id}"


class FinalIndustryEvaluation(TimeStampedModel):
    """
    Model for Final Industry Evaluation Form submitted by company supervisors
    at the end of internship. Scores range from 1-5.
    """

    internship = models.OneToOneField(
        Internship,
        on_delete=models.CASCADE,
        related_name="final_industry_evaluation",
        related_name="final_industry_evaluation",
    )
    company_mentor = models.ForeignKey(
        CompanyMentor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="final_evaluations",
        related_name="final_evaluations",
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=CompanyEvaluationStatus.choices,
        default=CompanyEvaluationStatus.SUBMITTED,
    )
    advisor_reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_final_industry_evaluations",
    )
    advisor_approved_at = models.DateTimeField(null=True, blank=True)
    advisor_rejected_at = models.DateTimeField(null=True, blank=True)
    visible_to_student = models.BooleanField(default=False)
    
    # SECTION A — JOB PERFORMANCE (1-5 scale)
    knowledge_about_task = models.PositiveIntegerField(default=0)
    problem_solving = models.PositiveIntegerField(default=0)
    quality_of_work = models.PositiveIntegerField(default=0)
    punctuality_in_production = models.PositiveIntegerField(default=0)
    initiative = models.PositiveIntegerField(default=0)

    # SECTION B — SOFT SKILLS (1-5 scale)
    dedication = models.PositiveIntegerField(default=0)
    cooperation = models.PositiveIntegerField(default=0)
    discipline = models.PositiveIntegerField(default=0)
    responsibility = models.PositiveIntegerField(default=0)
    socialization = models.PositiveIntegerField(default=0)
    communication = models.PositiveIntegerField(default=0)
    decision_making = models.PositiveIntegerField(default=0)

    # SECTION C — COMMENTS
    student_potential = models.TextField(blank=True)
    overall_comments = models.TextField(blank=True)
    would_offer_job = models.BooleanField(default=False)

    # CALCULATED FIELDS
    section_a_total = models.PositiveIntegerField(default=0)
    section_b_total = models.PositiveIntegerField(default=0)
    total_mark = models.PositiveIntegerField(default=0)
    overall_student_performance = models.DecimalField(
        max_digits=5, decimal_places=3, default=0
    )

    class Meta:
        verbose_name = "Final Industry Evaluation"
        verbose_name_plural = "Final Industry Evaluations"
        unique_together = ("internship",)

    def calculate_totals(self):
        """Calculate section totals and overall performance."""
        # Section A total (5 fields)
        self.section_a_total = (
            self.knowledge_about_task
            + self.problem_solving
            + self.quality_of_work
            + self.punctuality_in_production
            + self.initiative
        )

        # Section B total (7 fields)
        self.section_b_total = (
            self.dedication
            + self.cooperation
            + self.discipline
            + self.responsibility
            + self.socialization
            + self.communication
            + self.decision_making
        )

        # Total mark (Section A + Section B)
        self.total_mark = self.section_a_total + self.section_b_total

        # Overall student performance = (total_mark / 60) * 20
        # Max score is 60 (5*5 + 7*5), converted to 20 points scale
        if self.total_mark > 0:
            self.overall_student_performance = (self.total_mark / 60) * 20
        else:
            self.overall_student_performance = 0

    def save(self, *args, **kwargs):
        """Auto-calculate totals before saving."""
        self.calculate_totals()
        super().save(*args, **kwargs)
        from core.services.evaluation_workflow import sync_overall_from_company

        sync_overall_from_company(self)

    def __str__(self):
        return f"Final Industry Evaluation - {self.internship.student} ({self.internship.position.company.company_name})"


class Notification(models.Model):
    """Generic notification record for any system event."""

    class NotificationType(models.TextChoices):
        INTERNSHIP_STATUS_CHANGED = (
            "INTERNSHIP_STATUS_CHANGED",
            "Internship Status Changed",
        )
        REPORT_SUBMITTED = "REPORT_SUBMITTED", "Report Submitted"
        REPORT_REVIEWED = "REPORT_REVIEWED", "Report Reviewed"
        GENERAL = "GENERAL", "General"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=40,
        choices=NotificationType.choices,
        default=NotificationType.GENERAL,
    )
    is_read = models.BooleanField(default=False)
    # Optional – links this notification to any model instance
    related_object_id = models.PositiveIntegerField(null=True, blank=True)
    related_object_type = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read"]),
        ]

    def __str__(self):
        return f"[{self.notification_type}] {self.recipient} — {self.title}"
