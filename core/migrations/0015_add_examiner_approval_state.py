from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0014_drop_stale_advisor_score_constraints"),
    ]

    operations = [
        migrations.AddField(
            model_name="overallinternshipevaluation",
            name="examiner_approval_state",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
