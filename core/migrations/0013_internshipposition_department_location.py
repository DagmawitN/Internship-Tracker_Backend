from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0012_internshipposition_extra_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='internshipposition',
            name='department',
            field=models.CharField(max_length=150, blank=True),
        ),
        migrations.AddField(
            model_name='internshipposition',
            name='location',
            field=models.CharField(max_length=255, blank=True),
        ),
    ]
