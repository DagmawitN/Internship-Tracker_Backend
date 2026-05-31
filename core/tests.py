from django.core.exceptions import ValidationError
from django.test import TestCase

from core.evaluation_validators import validate_advisor_score_fields


class _AdvisorScoreStub:
	pass


class AdvisorEvaluationValidationTests(TestCase):
	def test_report_section_accepts_current_frontend_scale(self):
		stub = _AdvisorScoreStub()
		stub.report_format_score = 2
		stub.organization_background_score = 3
		stub.activities_score = 4
		stub.data_figure_table_score = 3
		stub.report_content_score = 4
		stub.recommendation_score = 2
		stub.conclusion_score = 3
		stub.pictures_and_data_score = 1
		stub.weekly_summary_score = 1
		stub.daily_detail_score = 1
		stub.improvement_score = 1
		stub.initiative_score = 1
		stub.understanding_objective_score = 4
		stub.engagement_score = 3
		stub.discipline_score = 3

		validate_advisor_score_fields(stub)

	def test_report_section_rejects_scores_above_updated_limit(self):
		stub = _AdvisorScoreStub()
		stub.report_format_score = 2
		stub.organization_background_score = 3
		stub.activities_score = 5
		stub.data_figure_table_score = 3
		stub.report_content_score = 4
		stub.recommendation_score = 2
		stub.conclusion_score = 3
		stub.pictures_and_data_score = 1
		stub.weekly_summary_score = 1
		stub.daily_detail_score = 1
		stub.improvement_score = 1
		stub.initiative_score = 1
		stub.understanding_objective_score = 4
		stub.engagement_score = 3
		stub.discipline_score = 3

		with self.assertRaises(ValidationError):
			validate_advisor_score_fields(stub)
