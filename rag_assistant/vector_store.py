"""
PostgreSQL + pgvector storage for the knowledge base.
"""
from django.db import connection
from pgvector.django import CosineDistance

from .models import KnowledgeBaseDocument

EMBEDDING_DIM = 1536  # voyage-large-2 embedding dimension


def upsert_document(doc_id: str, doc_type: str, title: str, content: str,
                    embedding: list[float], metadata: dict = None):
    """Insert or update a document in the knowledge base."""
    KnowledgeBaseDocument.objects.update_or_create(
        doc_id=doc_id,
        defaults={
            "type": doc_type,
            "title": title,
            "content": content,
            "embedding": embedding,
            "metadata": metadata or {},
        },
    )


def delete_document(doc_id: str):
    """Remove a document from the knowledge base."""
    KnowledgeBaseDocument.objects.filter(doc_id=doc_id).delete()


def vector_search(query_embedding: list[float], top_k: int = 5,
                  filter_type: str = None) -> list[dict]:
    """
    Run pgvector cosine-distance search and return top_k most similar documents.
    Optionally filter by document type.
    """
    queryset = KnowledgeBaseDocument.objects.all()
    if filter_type:
        queryset = queryset.filter(type=filter_type)

    results = (
        queryset
        .annotate(score=CosineDistance("embedding", query_embedding))
        .order_by("score")[:top_k]
    )

    return [
        {
            "doc_id": doc.doc_id,
            "type": doc.type,
            "title": doc.title,
            "content": doc.content,
            "metadata": doc.metadata or {},
            "score": float(doc.score) if doc.score is not None else None,
        }
        for doc in results
    ]


def ensure_vector_index():
    """
    Ensure the pgvector extension exists.
    """
    with connection.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    return True
