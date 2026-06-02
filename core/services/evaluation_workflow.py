"""
Workflow integration for advisor, examiner, company, and overall internship evaluations.
"""

from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from core.models import (
    AdvisorEvaluation,
    CompanyEvaluationStatus,
    ExaminerEvaluation,
    FinalIndustryEvaluation,
    InternshipApplication,
    OverallInternshipEvaluation,
    ReportReviewStatus,
)


def compute_final_grade(score):
    """Map numeric total (0–100) to letter grade."""
    s = float(score or 0)
    if s >= 90:
        return "A"
    if s >= 80:
        return "B"
    if s >= 70:
        return "C"
    if s >= 60:
        return "D"
    return "F"


def get_or_create_overall(internship):
    overall, _ = OverallInternshipEvaluation.objects.get_or_create(
        internship=internship,
        defaults={"status": OverallInternshipEvaluation.Status.PENDING_ADVISOR},
    )
    return overall


def sync_overall_from_advisor(advisor_eval):
    """Link approved advisor evaluation into overall workflow."""
    if not advisor_eval or not advisor_eval.internship_id:
        return
    overall = get_or_create_overall(advisor_eval.internship)
    overall.advisor_evaluation = advisor_eval
    overall.advisor_score = advisor_eval.final_weighted_mark
    if advisor_eval.status == AdvisorEvaluation.Status.APPROVED:
        overall.advisor_approved = True
        overall.advisor_approved_at = advisor_eval.approved_at
        overall.status = OverallInternshipEvaluation.Status.PENDING_EXAMINERS
    elif advisor_eval.status == AdvisorEvaluation.Status.REJECTED:
        overall.status = OverallInternshipEvaluation.Status.REJECTED
        overall.advisor_approved = False
    else:
        overall.status = OverallInternshipEvaluation.Status.PENDING_ADVISOR
        overall.advisor_approved = False
    overall.calculate_final()
    overall.save()


def sync_overall_from_examiner(internship_id):
    internship = InternshipApplication.objects.filter(pk=internship_id).first()
    if not internship:
        return
    overall = get_or_create_overall(internship)
    examiners = list(
        ExaminerEvaluation.objects.filter(internship=internship).order_by("submitted_at")[:2]
    )
    if len(examiners) >= 1:
        overall.examiner_one_evaluation = examiners[0]
    if len(examiners) >= 2:
        overall.examiner_two_evaluation = examiners[1]
    overall.examiner_completed = len(examiners) >= 2
    if overall.examiner_completed:
        overall.examiner_completed_at = timezone.now()
        if overall.advisor_approved:
            overall.status = OverallInternshipEvaluation.Status.PENDING_COORDINATOR
    overall.calculate_final()
    overall.save()


def sync_overall_from_company(company_eval):
    if not company_eval or not company_eval.internship_id:
        return
    # FinalIndustryEvaluation.internship is an Internship (execution) record,
    # but OverallInternshipEvaluation.internship is an InternshipApplication.
    # Resolve the application from the execution record.
    internship_record = company_eval.internship
    application = InternshipApplication.objects.filter(
        student=internship_record.student,
        position=internship_record.position,
    ).order_by("-id").first()
    if not application:
        return
    overall = get_or_create_overall(application)
    overall.company_evaluation = company_eval
    overall.company_final_score = company_eval.overall_student_performance
    
    # Calculate monthly average
    from core.models import CompanyEvaluationStatus, MonthlyIndustryEvaluation
    evals = MonthlyIndustryEvaluation.objects.filter(
        internship=application,
        status=CompanyEvaluationStatus.ADVISOR_APPROVED
    )
    if not evals.exists():
        evals = MonthlyIndustryEvaluation.objects.filter(internship=application)
    
    if evals.exists():
        performance_scores = []
        for e in evals:
            form_data = e.form_data or {}
            # Extract monthlyPerformance from form_data, fallback to total_score
            perf = form_data.get("monthlyPerformance")
            if perf is not None:
                performance_scores.append(float(perf))
            else:
                performance_scores.append(float(e.total_score))
        
        avg = sum(performance_scores) / len(performance_scores)
        overall.company_monthly_avg = Decimal(str(round(avg, 2)))
    else:
        overall.company_monthly_avg = Decimal("0")

    # Update company_score (Total)
    overall.company_score = (overall.company_monthly_avg or 0) + (overall.company_final_score or 0)
    
    overall.calculate_final()
    overall.save()


def can_coordinator_finalize(overall):
    """Coordinator may finalize only when all component evaluations are complete."""
    missing = []
    if not overall.advisor_approved:
        missing.append("advisor_evaluation_approved")
    if not overall.examiner_completed:
        missing.append("examiner_evaluations_completed")
    if overall.company_evaluation_id is None:
        missing.append("company_evaluation_submitted")
    elif overall.company_evaluation.status != CompanyEvaluationStatus.ADVISOR_APPROVED:
        missing.append("final_company_evaluation_advisor_approval")
    return len(missing) == 0, missing


def examiner_internship_queryset(user):
    """Internships the user may act on as examiner."""
    from core.models import AdvisorAssignment

    return InternshipApplication.objects.filter(
        advisor_assignments__advisor=user,
        advisor_assignments__role="EXAMINER",
    ).distinct()


def advisor_internship_queryset(user):
    """Internships the user may act on as advisor."""
    from core.models import Advisor, AdvisorAssignment

    assignment_ids = AdvisorAssignment.objects.filter(
        advisor=user, role="ADVISOR"
    ).values_list("internship_id", flat=True)

    advisor = Advisor.objects.filter(user=user).first()
    q = Q(pk__in=assignment_ids)
    if advisor:
        q |= Q(student__advisor=advisor) | Q(advisor=advisor)
    return InternshipApplication.objects.filter(q).distinct()


def build_advisor_queue_item(internship):
    """Build queue payload for one internship application."""
    from core.models import ExaminerEvaluation, Report, WeeklyLogbook

    student = internship.student
    company_name = internship.position.company.company_name
    advisor_eval = getattr(internship, "advisor_evaluation", None)
    overall = getattr(internship, "overall_evaluation", None)
    final_report = (
        Report.objects.filter(internship=internship, report_type="FINAL")
        .order_by("-submission_date")
        .first()
    )
    pending_logbooks = WeeklyLogbook.objects.filter(
        internship=internship,
        status__in=("SUBMITTED", "COMPANY_VERIFIED"),
    ).count()
    from core.models import MonthlyIndustryEvaluation

    monthly_reports = Report.objects.filter(
        internship=internship, report_type="MONTHLY"
    )
    monthly_evals = MonthlyIndustryEvaluation.objects.filter(internship=internship)
    company_eval = getattr(internship, "final_industry_evaluation", None)
    examiner_count = ExaminerEvaluation.objects.filter(internship=internship).count()

    pending_monthly_evals = monthly_evals.filter(
        status=CompanyEvaluationStatus.SUBMITTED
    ).count()
    pending_final_eval = (
        1
        if company_eval
        and company_eval.status == CompanyEvaluationStatus.SUBMITTED
        else 0
    )
    pending_final_report_examiner = 0
    if final_report and final_report.status == "SUBMITTED":
        pending_final_report_examiner = 1
    pending_reports = Report.objects.filter(
        internship=internship,
        report_type="MONTHLY",
        status="SUBMITTED",
    ).count()
    pending_final_advisor = (
        1
        if final_report
        and final_report.status == ReportReviewStatus.EXAMINER_APPROVED
        else 0
    )

    missing = []
    if not final_report:
        missing.append("final_report")
    if pending_logbooks > 0:
        missing.append("logbooks_pending_review")
    if not company_eval:
        missing.append("company_evaluation")
    elif company_eval.status != CompanyEvaluationStatus.ADVISOR_APPROVED:
        missing.append("final_evaluation_advisor_approval")
    if pending_monthly_evals > 0:
        missing.append("monthly_evaluations_advisor_approval")
    if pending_final_report_examiner > 0:
        missing.append("final_report_examiner_review")
    if pending_reports > 0 or pending_final_advisor > 0:
        missing.append("documents_advisor_approval")
    if examiner_count < 2:
        missing.append("examiner_evaluations_incomplete")
    if not advisor_eval:
        missing.append("advisor_evaluation")

    workflow_status = overall.status if overall else "NOT_STARTED"
    approval_stage = "ADVISOR_EVALUATION"
    if advisor_eval and advisor_eval.status == "APPROVED":
        approval_stage = "EXAMINER_REVIEW"
    if overall and overall.examiner_completed:
        approval_stage = "COORDINATOR_REVIEW"
    if overall and overall.coordinator_approved:
        approval_stage = "COMPLETED"

    return {
        "internship_id": internship.id,
        "student": {
            "id": student.id,
            "student_id": student.student_id,
            "full_name": (
                f"{student.user.first_name} {student.user.last_name}".strip()
                or student.user.username
            ),
        },
        "company": company_name,
        "timestamps": {
            "application_created": internship.created_at,
            "final_report_submitted": final_report.submission_date if final_report else None,
            "advisor_eval_submitted": advisor_eval.submitted_at if advisor_eval else None,
        },
        "approval_stage": approval_stage,
        "workflow_status": workflow_status,
        "pending_logbooks_count": pending_logbooks,
        "monthly_evaluations_count": monthly_evals.count(),
        "monthly_reports_count": monthly_reports.count(),
        "pending_monthly_evaluations": pending_monthly_evals,
        "pending_documents": pending_reports + pending_final_advisor,
        "pending_final_report_examiner": pending_final_report_examiner,
        "pending_final_evaluation": pending_final_eval,
        "examiner_evaluations_submitted": examiner_count,
        "examiner_evaluations_required": 2,
        "company_evaluation_submitted": company_eval is not None,
        "final_evaluation_status": company_eval.status if company_eval else None,
        "advisor_evaluation_status": advisor_eval.status if advisor_eval else None,
        "final_report_status": final_report.status if final_report else None,
        "missing_requirements": missing,
    }
