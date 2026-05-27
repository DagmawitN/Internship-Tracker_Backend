"""
Migration 0008: Align core_weeklylogbook table with the current model.

The DB was created with different column names than the current model definition.
We use RunSQL to rename columns directly and add the missing advisor_comment field.

DB has:    company_verified_at, advisor_reviewed_at  (no advisor_comment)
Model has: verified_at, reviewed_at, advisor_comment
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_fix_staff_is_assigned_column"),
    ]

    operations = [
        # Rename company_verified_at → verified_at in the actual DB
        migrations.RunSQL(
            sql="ALTER TABLE core_weeklylogbook RENAME COLUMN company_verified_at TO verified_at;",
            reverse_sql="ALTER TABLE core_weeklylogbook RENAME COLUMN verified_at TO company_verified_at;",
        ),
        # Rename advisor_reviewed_at → reviewed_at in the actual DB
        migrations.RunSQL(
            sql="ALTER TABLE core_weeklylogbook RENAME COLUMN advisor_reviewed_at TO reviewed_at;",
            reverse_sql="ALTER TABLE core_weeklylogbook RENAME COLUMN reviewed_at TO advisor_reviewed_at;",
        ),
        # Add the missing advisor_comment column
        migrations.RunSQL(
            sql="ALTER TABLE core_weeklylogbook ADD COLUMN IF NOT EXISTS advisor_comment TEXT NOT NULL DEFAULT '';",
            reverse_sql="ALTER TABLE core_weeklylogbook DROP COLUMN IF EXISTS advisor_comment;",
        ),
    ]
