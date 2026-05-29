from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0011_preregisteredstudent_email"),
    ]

    operations = [
        migrations.AddField(
            model_name="internshipposition",
            name="start_date",
            field=models.DateField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="internshipposition",
            name="end_date",
            field=models.DateField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="internshipposition",
            name="total_hours",
            field=models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="internshipposition",
            name="days_in_week",
            field=models.PositiveIntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="internshipposition",
            name="number_interns",
            field=models.PositiveIntegerField(null=True, blank=True),
        ),
    ]
