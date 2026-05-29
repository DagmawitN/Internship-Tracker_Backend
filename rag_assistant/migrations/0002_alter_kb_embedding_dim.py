from django.db import migrations
import pgvector.django


class Migration(migrations.Migration):
    dependencies = [
        ("rag_assistant", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="knowledgebasedocument",
            name="embedding",
            field=pgvector.django.VectorField(dimensions=1536),
        ),
    ]
