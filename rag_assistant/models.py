"""
PostgreSQL-backed knowledge base documents for the RAG assistant.
"""
from django.db import models
from pgvector.django import VectorField


class KnowledgeBaseDocument(models.Model):
    doc_id = models.CharField(max_length=255, unique=True)
    type = models.CharField(max_length=50, db_index=True)
    title = models.CharField(max_length=255)
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    embedding = VectorField(dimensions=1536)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rag_knowledge_base_document"
        ordering = ["doc_id"]

    def __str__(self) -> str:
        return f"{self.doc_id}: {self.title}"
