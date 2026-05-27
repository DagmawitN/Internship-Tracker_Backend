from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_dailylogentry_internshipposition_and_more"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE core_profile "
                        "ADD COLUMN IF NOT EXISTS full_name varchar(150) NOT NULL DEFAULT '';"
                    ),
                    reverse_sql="ALTER TABLE core_profile DROP COLUMN IF EXISTS full_name;",
                )
            ],
            state_operations=[
                migrations.AddField(
                    model_name="profile",
                    name="full_name",
                    field=models.CharField(blank=True, default="", max_length=150),
                )
            ],
        )
    ]