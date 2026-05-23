import random

from cloudinary.models import CloudinaryField
from cloudinary_storage.storage import RawMediaCloudinaryStorage
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

    # ---- Resume ----
    # RawMediaCloudinaryStorage ensures PDFs and DOCX files are uploaded
    # to Cloudinary with resource_type="raw" (not "image").
    resume = models.FileField(
        upload_to="resumes/",
        storage=RawMediaCloudinaryStorage(),
        null=True,
        blank=True,
    )
    resume_uploaded_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.student_id} - {self.user}"


class Skill(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class WorkMode(models.TextChoices):
    REMOTE = "REMOTE", _("Remote")
    ONSITE = "ONSITE", _("Onsite")
    HYBRID = "HYBRID", _("Hybrid")


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

    # Work mode
    work_mode = models.CharField(
        max_length=10,
        choices=WorkMode.choices,
        default=WorkMode.ONSITE,
    )

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

    # ---- Internship request form dates & schedule ----
    requested_start_date = models.DateField(null=True, blank=True)
    requested_end_date = models.DateField(null=True, blank=True)
    working_days_per_week = models.PositiveIntegerField(null=True, blank=True)
    working_hours_per_day = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True
    )

    # ---- Immutable snapshot of student/company/mentor at time of application ----
    form_snapshot = models.JSONField(default=dict, blank=True)

    # ---- Rejection reason (required when mentor rejects) ----
    rejection_reason = models.TextField(blank=True)

    # ---- Coordinator signature ----
    coordinator_signature = models.CharField(max_length=255, blank=True)
    coordinator_signed_at = models.DateTimeField(null=True, blank=True)

    # ---- Mentor signature ----
    mentor_signature = models.CharField(max_length=255, blank=True)
    mentor_signed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("student", "position")

    @property
    def overall_status(self):
        """Compute a unified application status from workflow states."""
        if self.student_decision == "DECLINED":
            return "DECLINED"
        if self.student_decision == "ACCEPTED":
            return "ACCEPTED"
        if (
            self.dept_status == "REJECTED"
            or self.mentor_status == "REJECTED"
            or self.advisor_status == "REJECTED"
        ):
            return "DECLINED"
        if self.mentor_status == "ACCEPTED":
            return "OFFER_RECEIVED"
        if self.dept_status == "APPROVED":
            return "AWAITING_MENTOR"
        return "PENDING"

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
    status = models.CharField(max_length=30, blank=True)  # e.g., SUBMITTED, REVIEWED
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_reports",
    )

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
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    communication_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    professionalism_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    problem_solving_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    overall_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
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
    Model for University Advisor Evaluation of internship performance.
    Submitted by assigned university advisor/supervisor.
    Scores range from 1-5.
    """

    # Basic Information
    internship = models.OneToOneField(
        InternshipApplication,
        on_delete=models.CASCADE,
        related_name="advisor_evaluation",
    )
    advisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_advisor_evaluations",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)

    # Evaluation Scores (1-5 scale)
    technical_followup_score = models.PositiveIntegerField(default=0)
    communication_score = models.PositiveIntegerField(default=0)
    attendance_followup_score = models.PositiveIntegerField(default=0)
    professionalism_score = models.PositiveIntegerField(default=0)
    report_quality_score = models.PositiveIntegerField(default=0)

    # Comments
    comments = models.TextField(blank=True)

    # Calculated Fields
    total_score = models.PositiveIntegerField(default=0)
    weighted_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Advisor Evaluation"
        verbose_name_plural = "Advisor Evaluations"
        unique_together = ("internship",)

    def calculate_scores(self):
        """Calculate total and weighted scores."""
        # Total score (sum of 5 components, each 1-5, max = 25)
        self.total_score = (
            self.technical_followup_score
            + self.communication_score
            + self.attendance_followup_score
            + self.professionalism_score
            + self.report_quality_score
        )

        # Weighted score = (total_score / 25) * 20
        # Converts 25-point scale to 20-point scale
        if self.total_score > 0:
            self.weighted_score = (self.total_score / 25) * 20
        else:
            self.weighted_score = 0

    def save(self, *args, **kwargs):
        """Auto-calculate scores before saving."""
        self.calculate_scores()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Advisor Evaluation - {self.internship.student} by {self.advisor}"


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


class FinalIndustryEvaluation(TimeStampedModel):
    """
    Model for Final Industry Evaluation Form submitted by company supervisors
    at the end of internship. Scores range from 1-5.
    """

    # Basic Information
    internship = models.OneToOneField(
        Internship,
        on_delete=models.CASCADE,
        related_name="final_industry_evaluation",
    )
    company_mentor = models.ForeignKey(
        CompanyMentor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="final_evaluations",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)

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
        max_digits=5, decimal_places=2, default=0
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


class AuditLog(models.Model):
    """Centralized audit trail for important system actions."""

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=100)
    target_type = models.CharField(max_length=100, blank=True)
    target_id = models.PositiveIntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["actor"]),
            models.Index(fields=["action"]),
        ]

    def __str__(self):
        return f"[{self.action}] by {self.actor} at {self.timestamp}"
