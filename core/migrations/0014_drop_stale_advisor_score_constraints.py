from django.db import migrations


STALE_ADVISOR_SCORE_CONSTRAINTS = [
    "advisor_activities_score_range",
    "advisor_conclusion_score_range",
    "advisor_daily_detail_score_range",
    "advisor_data_figure_table_score_range",
    "advisor_discipline_score_range",
    "advisor_engagement_score_range",
    "advisor_improvement_score_range",
    "advisor_initiative_score_range",
    "advisor_organization_background_score_range",
    "advisor_pictures_and_data_score_range",
    "advisor_recommendation_score_range",
    "advisor_report_content_score_range",
    "advisor_report_format_score_range",
    "advisor_understanding_objective_score_range",
    "advisor_weekly_summary_score_range",
]


def drop_stale_constraints(apps, schema_editor):
    table_name = "core_advisorevaluation"
    with schema_editor.connection.cursor() as cursor:
        for constraint_name in STALE_ADVISOR_SCORE_CONSTRAINTS:
            cursor.execute(
                f'ALTER TABLE "{table_name}" DROP CONSTRAINT IF EXISTS "{constraint_name}";'
            )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0013_internshipposition_department_location"),
    ]

    operations = [
        migrations.RunPython(drop_stale_constraints, migrations.RunPython.noop),
    ]