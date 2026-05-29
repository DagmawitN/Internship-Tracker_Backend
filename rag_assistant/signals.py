"""
Django signals to auto-index internships when they are created/updated/deleted.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver


def _safe_index(position):
    """Index without crashing the main request if RAG services are unavailable."""
    try:
        from .knowledge_base import index_internship
        index_internship(position)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"RAG indexing failed for position {position.id}: {e}")


def _safe_remove(position_id):
    try:
        from .knowledge_base import remove_internship
        remove_internship(position_id)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"RAG removal failed for position {position_id}: {e}")


# Connect signals lazily to avoid circular imports at startup
def connect_signals():
    from core.models import InternshipPosition

    @receiver(post_save, sender=InternshipPosition, weak=False)
    def on_internship_saved(sender, instance, **kwargs):
        _safe_index(instance)

    @receiver(post_delete, sender=InternshipPosition, weak=False)
    def on_internship_deleted(sender, instance, **kwargs):
        _safe_remove(instance.id)
