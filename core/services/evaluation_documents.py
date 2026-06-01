"""Serialization helpers for advisor queue and student evaluation visibility."""

from core.models import (
    CompanyEvaluationStatus,
    ExaminerEvaluation,
    FinalIndustryEvaluation,
    MonthlyIndustryEvaluation,
    OverallInternshipEvaluation,
    Report,
    WeeklyLogbook,
)


def _student_can_see_scores(internship):
    overall = getattr(internship, "overall_evaluation", None)
    return bool(
        overall
        and overall.coordinator_approved
        and overall.visible_to_student
    )


def serialize_company_evaluation(eval_obj, internship, *, include_scores=None):
    """Build company eval payload; scores only when coordinator has finalized."""
    if eval_obj is None:
        return None
    show_scores = (
        include_scores
        if include_scores is not None
        else _student_can_see_scores(internship)
    )
    data = {
        "id": eval_obj.id,
        "status": eval_obj.status,
        "submitted_at": eval_obj.submitted_at,
        "advisor_approved_at": eval_obj.advisor_approved_at,
        "advisor_rejected_at": getattr(eval_obj, "advisor_rejected_at", None),
        "visible_to_student": eval_obj.visible_to_student,
        "show_scores": show_scores,
    }
    if isinstance(eval_obj, MonthlyIndustryEvaluation):
        data["month_number"] = eval_obj.month_number
    if show_scores:
        if isinstance(eval_obj, MonthlyIndustryEvaluation):
            data.update(
                {
                    "work_quality_score": eval_obj.work_quality_score,
                    "punctuality_score": eval_obj.punctuality_score,
                    "attitude_score": eval_obj.attitude_score,
                    "initiative_score": eval_obj.initiative_score,
                    "total_score": eval_obj.total_score,
                    "comments": eval_obj.comments,
                }
            )
        elif isinstance(eval_obj, FinalIndustryEvaluation):
            data["total_mark"] = eval_obj.total_mark
            data["overall_student_performance"] = eval_obj.overall_student_performance
    return data


def serialize_report_document(report):
    if report is None:
        return None
    file_urls = []
    if hasattr(report, "files"):
        file_urls = [f.file.url for f in report.files.all() if f.file]
    return {
        "id": report.id,
        "report_type": report.report_type,
        "title": report.title,
        "status": report.status,
        "submission_date": report.submission_date,
        "reviewed_at": report.reviewed_at,
        "approved_at": report.approved_at,
        "rejected_at": report.rejected_at,
        "examiner_approved_at": report.examiner_approved_at,
        "examiner_rejected_at": report.examiner_rejected_at,
        "examiner_reviewer_id": report.examiner_reviewer_id,
        "advisor_comment": report.advisor_comment,
        "advisor_comment_at": report.advisor_comment_at,
        "advisor_comment_by_id": report.advisor_comment_by_id,
        "file_urls": file_urls,
        "week_number": report.week_number,
    }


def serialize_logbook_document(logbook):
    return {
        "id": logbook.id,
        "week_number": logbook.week_number,
        "status": logbook.status,
        "submitted_at": logbook.submitted_at,
        "verified_at": logbook.verified_at,
        "reviewed_at": getattr(logbook, "reviewed_at", None)
        or getattr(logbook, "advisor_reviewed_at", None),
    }


def serialize_examiner_evaluation(ev, *, include_scores=True):
    if ev is None:
        return None
    data = {
        "id": ev.id,
        "examiner_id": ev.examiner_id,
        "examiner_name": (
            ev.examiner.get_full_name() or ev.examiner.username if ev.examiner else ""
        ),
        "submitted_at": ev.submitted_at,
        "comments": ev.comments if include_scores else None,
        "form_data": ev.form_data if include_scores else None,
    }
    if include_scores:
        data.update(
            {
                "technical_skills_score": ev.technical_skills_score,
                "communication_score": ev.communication_score,
                "professionalism_score": ev.professionalism_score,
                "report_quality_score": ev.report_quality_score,
                "presentation_score": ev.presentation_score,
                "total_score": ev.total_score,
                "weighted_score": ev.weighted_score,
            }
        )
    return data


def build_documents_section(internship):
    final_report = (
        Report.objects.filter(internship=internship, report_type="FINAL")
        .order_by("-submission_date")
        .first()
    )
    monthly_reports = Report.objects.filter(
        internship=internship, report_type="MONTHLY"
    ).order_by("week_number", "-submission_date")
    logbooks = WeeklyLogbook.objects.filter(internship=internship).order_by(
        "week_number"
    )
    return {
        "final_report": serialize_report_document(final_report),
        "monthly_reports": [serialize_report_document(r) for r in monthly_reports],
        "weekly_logbooks": [serialize_logbook_document(lb) for lb in logbooks],
    }


def build_company_evaluations_section(internship, *, for_student=False):
    monthly = MonthlyIndustryEvaluation.objects.filter(
        internship=internship
    ).order_by("month_number")
    final_eval = getattr(internship, "final_industry_evaluation", None)
    include_scores = not for_student or _student_can_see_scores(internship)
    return {
        "monthly_evaluations": [
            serialize_company_evaluation(m, internship, include_scores=include_scores)
            for m in monthly
        ],
        "final_evaluation": serialize_company_evaluation(
            final_eval, internship, include_scores=include_scores
        ),
    }


def build_examiner_section(internship, *, for_student=False):
    show_scores = not for_student or _student_can_see_scores(internship)
    examiners = ExaminerEvaluation.objects.filter(internship=internship).order_by(
        "submitted_at"
    )
    overall = getattr(internship, "overall_evaluation", None)
    return {
        "evaluations": [
            serialize_examiner_evaluation(e, include_scores=show_scores)
            for e in examiners
        ],
        "submitted_count": examiners.count(),
        "required_count": 2,
        "completed": bool(overall and overall.examiner_completed),
        "examiner_completed_at": (
            overall.examiner_completed_at if overall else None
        ),
    }


def build_student_evaluation_status(internship):
    """Status and timestamps visible after advisor approval; scores after coordinator."""
    monthly = MonthlyIndustryEvaluation.objects.filter(
        internship=internship
    ).order_by("month_number")
    final_eval = getattr(internship, "final_industry_evaluation", None)
    show_scores = _student_can_see_scores(internship)

    def _public_company_view(ev):
        if ev is None:
            return None
        payload = {
            "id": ev.id,
            "status": ev.status,
            "submitted_at": ev.submitted_at,
            "advisor_approved_at": ev.advisor_approved_at,
            "advisor_rejected_at": ev.advisor_rejected_at,
            "show_scores": show_scores,
        }
        if isinstance(ev, MonthlyIndustryEvaluation):
            payload["month_number"] = ev.month_number
        if ev.status == CompanyEvaluationStatus.SUBMITTED:
            payload["message"] = "Submitted by company; pending advisor approval."
            return payload
        if ev.status == CompanyEvaluationStatus.REJECTED:
            payload["message"] = "Rejected by advisor."
            return payload
        if ev.status == CompanyEvaluationStatus.ADVISOR_APPROVED:
            payload["message"] = "Approved by advisor."
            if show_scores:
                payload.update(
                    serialize_company_evaluation(
                        ev, internship, include_scores=True
                    )
                )
            return payload
        return payload

    final_report = (
        Report.objects.filter(internship=internship, report_type="FINAL")
        .order_by("-submission_date")
        .first()
    )
    overall = getattr(internship, "overall_evaluation", None)
    return {
        "internship_id": internship.id,
        "coordinator_approved": bool(
            overall and overall.coordinator_approved and overall.visible_to_student
        ),
        "coordinator_approved_at": (
            overall.coordinator_approved_at if overall else None
        ),
        "documents": build_documents_section(internship),
        "final_report_review": serialize_report_document(final_report),
        "monthly_evaluations": [_public_company_view(m) for m in monthly],
        "final_evaluation": _public_company_view(final_eval),
        "examiner_progress": build_examiner_section(internship, for_student=True),
    }


def build_advisor_queue_detail(internship):
    """Full advisor queue item with documents, company evals, and examiner results."""
    from core.services.evaluation_workflow import build_advisor_queue_item

    base = build_advisor_queue_item(internship)
    base["documents"] = build_documents_section(internship)
    base["company_evaluations"] = build_company_evaluations_section(internship)
    base["examiner_evaluations"] = build_examiner_section(internship, for_student=False)
    overall = getattr(internship, "overall_evaluation", None)
    base["overall_evaluation"] = {
        "status": overall.status if overall else "NOT_STARTED",
        "advisor_approved": overall.advisor_approved if overall else False,
        "examiner_completed": overall.examiner_completed if overall else False,
        "coordinator_approved": overall.coordinator_approved if overall else False,
        "final_total_score": (
            str(overall.final_total_score) if overall and overall.final_total_score else None
        ),
        "final_grade": overall.final_grade if overall else None,
    }
    return base
