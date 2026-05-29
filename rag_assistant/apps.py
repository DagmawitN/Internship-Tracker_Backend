from django.apps import AppConfig


class RagAssistantConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "rag_assistant"
    verbose_name = "RAG Internship Assistant"

    def ready(self):
        from .signals import connect_signals
        connect_signals()
