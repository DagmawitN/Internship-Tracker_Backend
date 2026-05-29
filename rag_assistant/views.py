"""
RAG Assistant API views.
"""
import json
import os
from datetime import date

from django.db.models import Q
from rest_framework import status
from rest_framework.parsers import MultiPartParser, JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .cv_parser import extract_text_from_pdf, parse_cv
from .embeddings import embed_query
from .gemini_client import (
    answer_question,
    classify_internship_intent,
    generate_recommendation_summary,
    greeting_reply,
    internship_only_reply,
    is_greeting_question,
)
from .matcher import match_internships
from .vector_store import vector_search


def _is_internship_listing_question(question: str) -> bool:
    classification = classify_internship_intent(question)
    if classification.get("is_internship_search"):
        return True

    normalized = " ".join((question or "").strip().lower().split())
    if not normalized:
        return False
    listing_phrases = (
        "available internship",
        "available internships",
        "list internships",
        "list of internships",
        "what internships",
        "show internships",
        "internships available",
        "open internships",
        "current internships",
        "i want internship",
        "i want internships",
        "need internship",
        "looking for internship",
        "looking for internships",
    )
    return "internship" in normalized or any(phrase in normalized for phrase in listing_phrases)


def _parse_internship_filters(question: str) -> dict:
    classification = classify_internship_intent(question)
    normalized = " ".join((question or "").strip().lower().split())
    filters = {
        "remote": bool(classification.get("remote", False)),
        "part_time": bool(classification.get("part_time", False)),
        "next_month": bool(classification.get("next_month", False)),
        "location": classification.get("location") or None,
    }

    if any(token in normalized for token in ("online", "remote", "work from home", "wfh")):
        filters["remote"] = True

    if any(token in normalized for token in ("part time", "part-time", "parttime")):
        filters["part_time"] = True

    if "next month" in normalized or "coming month" in normalized:
        filters["next_month"] = True

    for marker in (" in ", " at ", " near "):
        if marker in normalized:
            tail = normalized.split(marker, 1)[1]
            tail = tail.split(" and ", 1)[0].split(",", 1)[0].strip()
            if tail and len(tail.split()) <= 4:
                filters["location"] = filters["location"] or tail
                break

    return filters


def _format_internship_listing_response(question: str) -> dict:
    from core.models import InternshipPosition

    filters = _parse_internship_filters(question)
    queryset = (
        InternshipPosition.objects.select_related("company")
        .prefetch_related("required_skills")
        .filter(is_active=True)
        .order_by("-created_at")
    )

    if filters["remote"]:
        queryset = queryset.filter(Q(is_remote=True) | Q(work_mode__in=["REMOTE", "HYBRID"]))
    if filters["part_time"]:
        queryset = queryset.filter(days_in_week__lte=3)
    if filters["next_month"]:
        today = date.today()
        if today.month == 12:
            next_month_start = date(today.year + 1, 1, 1)
        else:
            next_month_start = date(today.year, today.month + 1, 1)
        if next_month_start.month == 12:
            following_month_start = date(next_month_start.year + 1, 1, 1)
        else:
            following_month_start = date(next_month_start.year, next_month_start.month + 1, 1)
        queryset = queryset.filter(
            start_date__gte=next_month_start,
            start_date__lt=following_month_start,
        )
    if filters["location"]:
        queryset = queryset.filter(location__icontains=filters["location"])

    positions = list(queryset[:10])
    no_exact_matches = False
    if not positions:
        no_exact_matches = True
        positions = list(
            InternshipPosition.objects.select_related("company")
            .prefetch_related("required_skills")
            .filter(is_active=True)
            .order_by("-created_at")[:10]
        )

    if not positions:
        return {
            "answer": "I couldn’t find any available internships right now.",
            "sources": [],
        }

    lines = []
    if no_exact_matches:
        lines.append("### Available Internships")
        lines.append("I couldn’t find an exact match for those filters, so here are the currently available internships:")
    else:
        lines.append("### Available Internships")

    filter_notes = []
    if filters["remote"]:
        filter_notes.append("online/remote")
    if filters["part_time"]:
        filter_notes.append("part-time")
    if filters["next_month"]:
        filter_notes.append("starting next month")
    if filters["location"]:
        filter_notes.append(f"location: {filters['location']}")
    if filter_notes:
        lines.append(f"_Filters: {', '.join(filter_notes)}_")

    sources = []
    for position in positions:
        skills = list(position.required_skills.values_list("name", flat=True))
        work_mode = str(getattr(position, "work_mode", "ONSITE") or "ONSITE").lower()
        location = position.location or ""
        start_date = position.start_date.isoformat() if position.start_date else ""
        company_name = position.company.company_name
        extra_bits = []
        if location:
            extra_bits.append(location)
        if work_mode:
            extra_bits.append(work_mode)
        if start_date:
            extra_bits.append(f"starts {start_date}")
        details = f" ({', '.join(extra_bits)})" if extra_bits else ""
        lines.append(f"- **{position.title}** at **{company_name}**{details}")
        if skills:
            lines.append(f"  - Skills: {', '.join(skills[:6])}")
        lines.append("")
        sources.append({
            "title": position.title,
            "type": "internship",
            "score": 1.0,
        })

    return {"answer": "\n".join(lines).strip(), "sources": sources}


class AskQuestionView(APIView):
    """
    POST /api/assistant/ask/
    Body: { "question": "..." }
    Returns: { "answer": "..." }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        question = (request.data.get("question") or "").strip()
        if not question:
            return Response(
                {"error": "question field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if is_greeting_question(question):
            return Response(
                {
                    "answer": greeting_reply(),
                    "sources": [],
                }
            )

        if _is_internship_listing_question(question):
            return Response(_format_internship_listing_response(question))

        try:
            # Embed the question and retrieve relevant documents
            query_embedding = embed_query(question)
            docs = vector_search(query_embedding, top_k=5)

            # Generate answer using Gemini or the internship-only fallback
            answer = answer_question(question, docs)

            if not docs or answer == internship_only_reply():
                answer = internship_only_reply()
                docs = []

            return Response({
                "answer": answer,
                "sources": [
                    {"title": d.get("title"), "type": d.get("type"), "score": d.get("score")}
                    for d in docs
                ],
            })
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            # Provide a clearer hint about the GEMINI API key while masking it.
            def _mask_key(k: str) -> str:
                try:
                    if not k or len(k) < 8:
                        return "****"
                    return f"{k[:4]}...{k[-4:]}"
                except Exception:
                    return "****"

            api_key = os.environ.get("GEMINI_API_KEY")
            masked = _mask_key(api_key)
            return Response(
                {
                    "error": f"Assistant error: {str(e)}.",
                    "gemini_key_env": f"GEMINI_API_KEY (masked): {masked}",
                    "hint": "Ensure GEMINI_API_KEY is set in the environment and is valid."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CVAnalysisView(APIView):
    """
    POST /api/assistant/cv/
    Multipart: cv_file (PDF)
    Returns: { "cv_data": {...}, "recommendations": [...], "summary": "..." }
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, JSONParser]

    def post(self, request):
        cv_file = request.FILES.get("cv_file")
        if not cv_file:
            return Response(
                {"error": "cv_file is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not cv_file.name.lower().endswith(".pdf"):
            return Response(
                {"error": "Only PDF files are supported."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Extract text from PDF
            file_bytes = cv_file.read()
            cv_text = extract_text_from_pdf(file_bytes)

            if not cv_text.strip():
                return Response(
                    {"error": "Could not extract text from the PDF."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Parse CV with Gemini
            cv_data = parse_cv(cv_text)

            # Match against internship knowledge base
            recommendations = match_internships(cv_data, top_k=5)

            # Generate natural language summary
            summary = generate_recommendation_summary(cv_data, recommendations)

            return Response({
                "cv_data": {
                    "name": cv_data.get("name", ""),
                    "skills": cv_data.get("skills", []),
                    "education": cv_data.get("education", []),
                    "experience": cv_data.get("experience", []),
                    "certifications": cv_data.get("certifications", []),
                    "projects": cv_data.get("projects", []),
                },
                "recommendations": recommendations,
                "summary": summary,
            })

        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            return Response(
                {"error": f"CV analysis error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class IndexKnowledgeBaseView(APIView):
    """
    POST /api/assistant/index/
    Admin-only: re-index all internships and process documents.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Only admins can trigger re-indexing
        role = getattr(getattr(request.user, "role", None), "role_name", "")
        if role not in ("ADMIN", "COORDINATOR"):
            return Response(
                {"error": "Only admins and coordinators can trigger indexing."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            from .knowledge_base import index_all_internships, index_all_process_documents
            index_all_process_documents()
            index_all_internships()
            return Response({"message": "Knowledge base indexed successfully."})
        except Exception as e:
            return Response(
                {"error": f"Indexing error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class InternshipRecommendView(APIView):
    """
    POST /api/assistant/recommend/
    Body: { "skills": ["Python", "Django", ...] }
    Returns recommendations without requiring a CV upload.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        skills = request.data.get("skills", [])
        if not skills:
            return Response(
                {"error": "skills list is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            cv_data = {"skills": skills, "technologies": skills}
            recommendations = match_internships(cv_data, top_k=5)
            return Response({"recommendations": recommendations})
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
