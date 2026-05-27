from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_profile_full_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="internshipapplication",
            name="reason_for_joining",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="internshipapplication",
            name="cv_file",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="internship_applications/cvs/",
            ),
        ),
    ]