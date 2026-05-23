"""
Score limits for AASTU VPAA/DPT/OF/003 Advisor Supervisor Internship Evaluation Form.
Section weights: Report 20%, Logbook 5%, Student Performance 10% (35% total).
"""

# Section 1 — Report Evaluation (raw max 20 → weighted 20%)
REPORT_SCORE_FIELDS = {
    "report_format_score": 3,
    "organization_background_score": 3,
    "activities_score": 3,
    "data_figure_table_score": 3,
    "report_content_score": 3,
    "recommendation_score": 2,
    "conclusion_score": 3,
}
REPORT_SECTION_MAX = sum(REPORT_SCORE_FIELDS.values())  # 20

# Section 2 — Logbook Evaluation (raw max 5 → weighted 5%)
LOGBOOK_SCORE_FIELDS = {
    "pictures_and_data_score": 1,
    "weekly_summary_score": 1,
    "daily_detail_score": 1,
    "improvement_score": 1,
    "initiative_score": 1,
}
LOGBOOK_SECTION_MAX = sum(LOGBOOK_SCORE_FIELDS.values())  # 5

# Section 3 — Student Performance (raw max 10 → weighted 10%)
PERFORMANCE_SCORE_FIELDS = {
    "understanding_objective_score": 4,
    "engagement_score": 3,
    "discipline_score": 3,
}
PERFORMANCE_SECTION_MAX = sum(PERFORMANCE_SCORE_FIELDS.values())  # 10

ADVISOR_SCORE_FIELDS = {
    **REPORT_SCORE_FIELDS,
    **LOGBOOK_SCORE_FIELDS,
    **PERFORMANCE_SCORE_FIELDS,
}

ADVISOR_TOTAL_RAW_MAX = REPORT_SECTION_MAX + LOGBOOK_SECTION_MAX + PERFORMANCE_SECTION_MAX  # 35
ADVISOR_FINAL_WEIGHTED_MAX = ADVISOR_TOTAL_RAW_MAX  # weighted marks equal raw section totals

# Examiner evaluation (5 criteria × 5 pts; two examiners → 45% combined)
EXAMINER_SCORE_FIELDS = {
    "technical_skills_score": 5,
    "communication_score": 5,
    "professionalism_score": 5,
    "report_quality_score": 5,
    "presentation_score": 5,
}
EXAMINER_RAW_MAX = sum(EXAMINER_SCORE_FIELDS.values())  # 25
EXAMINER_WEIGHTED_MAX = 22.5  # per examiner slot (45% / 2)

COMPANY_WEIGHTED_MAX = 20  # from FinalIndustryEvaluation.overall_student_performance
