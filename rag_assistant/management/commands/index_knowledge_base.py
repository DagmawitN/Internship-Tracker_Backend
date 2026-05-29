"""
Management command: python manage.py index_knowledge_base

Indexes all internship positions and process documents into PostgreSQL
with pgvector. Run this once after setup, then it auto-updates via signals.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Index all internship positions and process documents into the RAG knowledge base."

    def add_arguments(self, parser):
        parser.add_argument(
            "--internships-only",
            action="store_true",
            help="Only index internship positions, skip process documents.",
        )
        parser.add_argument(
            "--process-only",
            action="store_true",
            help="Only index process/FAQ documents, skip internship positions.",
        )
        parser.add_argument(
            "--create-index",
            action="store_true",
            help="Ensure the PostgreSQL pgvector extension exists.",
        )

    def handle(self, *args, **options):
        from rag_assistant.knowledge_base import (
            index_all_internships,
            index_all_process_documents,
        )

        if options["create_index"]:
            self.stdout.write("Ensuring PostgreSQL pgvector extension exists...")
            try:
                from rag_assistant.vector_store import ensure_vector_index
                created = ensure_vector_index()
                if created:
                    self.stdout.write(self.style.SUCCESS("pgvector extension is ready."))
                else:
                    self.stdout.write("pgvector extension already exists.")
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Index creation failed: {e}"))
                return

        if not options["internships_only"]:
            self.stdout.write("Indexing process documents...")
            try:
                index_all_process_documents()
                self.stdout.write(self.style.SUCCESS("Process documents indexed."))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Process doc indexing failed: {e}"))

        if not options["process_only"]:
            self.stdout.write("Indexing internship positions...")
            try:
                from core.models import InternshipPosition
                count = InternshipPosition.objects.count()
                index_all_internships()
                self.stdout.write(self.style.SUCCESS(f"Indexed {count} internship position(s)."))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Internship indexing failed: {e}"))

        self.stdout.write(self.style.SUCCESS("Knowledge base indexing complete."))
