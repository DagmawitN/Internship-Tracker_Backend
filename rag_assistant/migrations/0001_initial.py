from django.contrib.postgres.operations import CreateExtension
from django.db import migrations, models
import pgvector.django


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        CreateExtension("vector"),
        migrations.CreateModel(
            name="KnowledgeBaseDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("doc_id", models.CharField(max_length=255, unique=True)),
                ("type", models.CharField(db_index=True, max_length=50)),
                ("title", models.CharField(max_length=255)),
                ("content", models.TextField()),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("embedding", pgvector.django.VectorField(dimensions=1024)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "rag_knowledge_base_document",
                "ordering": ["doc_id"],
            },
        ),
    ]
