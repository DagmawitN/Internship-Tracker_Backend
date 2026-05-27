from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_staff_is_assigned"),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE core_staff ADD COLUMN IF NOT EXISTS is_assigned boolean NOT NULL DEFAULT false;",
            reverse_sql="ALTER TABLE core_staff DROP COLUMN IF EXISTS is_assigned;",
        ),
    ]