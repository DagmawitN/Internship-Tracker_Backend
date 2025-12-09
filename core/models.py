# core/models.py
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


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
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    role = models.ForeignKey(UserRole, on_delete=models.PROTECT, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    last_login = models.DateTimeField(null=True, blank=True)

  
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self):
        return self.username or self.email


class Admin(models.Model):
 
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="admin_profile")
    admin_level = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"Admin: {self.user}"


class Department(TimeStampedModel):
    department_code = models.CharField(max_length=20)
    department_name = models.CharField(max_length=100)
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
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="company_mentorships")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="mentors")
    position = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.user} - {self.company}"


class Supervisor(TimeStampedModel):

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="supervisions")
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    supervisor_type = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"Supervisor: {self.user}"


class Student(TimeStampedModel):
 
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="student_profile")
    student_id = models.CharField(max_length=20)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="students")
    

    def __str__(self):
        return f"{self.student_number} - {self.user}"


class Internship(TimeStampedModel):
 
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("ONGOING", "Ongoing"),
        ("COMPLETED", "Completed"),
        ("CANCELLED", "Cancelled"),
    ]

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="internships")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="internships")
    supervisor = models.ForeignKey(Supervisor, on_delete=models.SET_NULL, null=True, blank=True, related_name="internships")
    mentor = models.ForeignKey(CompanyMentor, on_delete=models.SET_NULL, null=True, blank=True, related_name="internships")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="PENDING")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    application_date = models.DateTimeField(null=True, blank=True)
    approval_date = models.DateTimeField(null=True, blank=True)
    completion_date = models.DateTimeField(null=True, blank=True)
    total_hours = models.IntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Internship {self.id} - {self.student}"


class Attendance(TimeStampedModel):
  
    internship = models.ForeignKey(Internship, on_delete=models.CASCADE, related_name="attendances")
    date = models.DateField()
    check_in_time = models.TimeField(null=True, blank=True)
    check_out_time = models.TimeField(null=True, blank=True)
    hours_worked = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=30, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Attendance {self.id} - {self.internship} - {self.date}"


class AttendanceLocation(TimeStampedModel):

    attendance = models.ForeignKey(Attendance, on_delete=models.CASCADE, related_name="locations")
    latitude = models.DecimalField(max_digits=10, decimal_places=8)
    longitude = models.DecimalField(max_digits=11, decimal_places=8)
    accuracy = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
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

    internship = models.ForeignKey(Internship, on_delete=models.CASCADE, related_name="reports")
    week_number = models.IntegerField(null=True, blank=True)
    submission_date = models.DateTimeField(null=True, blank=True)
    report_type = models.CharField(max_length=30, choices=REPORT_TYPES, default="WEEKLY")
    title = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=30, blank=True)  # e.g., SUBMITTED, REVIEWED
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_reports")

    def __str__(self):
        return f"Report {self.id} - {self.internship}"


class ReportFile(TimeStampedModel):

    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name="files")
    file_name = models.CharField(max_length=200)
    file_path = models.CharField(max_length=255)  # or use FileField
    file_size = models.BigIntegerField(null=True, blank=True)
    mime_type = models.CharField(max_length=100, blank=True)
    uploaded_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.file_name


class ReportFeedback(TimeStampedModel):
 
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name="feedbacks")
    supervisor = models.ForeignKey(Supervisor, on_delete=models.SET_NULL, null=True, blank=True)
    feedback_text = models.TextField(blank=True)

    def __str__(self):
        return f"Feedback {self.id} on {self.report}"


class Evaluation(TimeStampedModel):

    EVAL_TYPES = [
        ("MIDTERM", "Midterm"),
        ("FINAL", "Final"),
        ("OTHER", "Other"),
    ]

    internship = models.ForeignKey(Internship, on_delete=models.CASCADE, related_name="evaluations")
    supervisor = models.ForeignKey(Supervisor, on_delete=models.SET_NULL, null=True, blank=True)
    evaluation_type = models.CharField(max_length=30, choices=EVAL_TYPES, default="FINAL")
    technical_skills_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    communication_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    professionalism_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    problem_solving_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    overall_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    general_feedback = models.TextField(blank=True)
    strengths = models.TextField(blank=True)
    areas_for_improvement = models.TextField(blank=True)
    evaluation_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"Evaluation {self.id} - {self.internship}"

class AdvisorAssignment(TimeStampedModel):

    coordinator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="coordinator_assignments")
    advisor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="advisor_assignments")
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="advisor_for_student")
    internship = models.ForeignKey(Internship, on_delete=models.CASCADE, related_name="advisor_assignments")
    assigned_at = models.DateTimeField(auto_now_add=True)
    role = models.CharField(max_length=30, choices=[("ADVISOR", "Advisor"), ("EXAMINER", "Examiner")], default="ADVISOR")

    class Meta:
        unique_together = ("advisor", "internship")

    def __str__(self):
        return f"{self.role} {self.advisor} assigned to {self.student} for {self.internship}"


class AdvisorEvaluation(TimeStampedModel):
   
    advisor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="advisor_evaluations")
    internship = models.ForeignKey(Internship, on_delete=models.CASCADE, related_name="advisor_evaluations")
    evaluation_date = models.DateField(null=True, blank=True)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    comments = models.TextField(blank=True)

    def __str__(self):
        return f"AdvisorEvaluation {self.id} by {self.advisor} for {self.internship}"

class Meta:
    pass
