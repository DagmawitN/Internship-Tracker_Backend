"""
Gemini 2.5 Flash client for RAG question answering.
"""
import os
import google.generativeai as genai

SYSTEM_PROMPT = """You are an AI Internship Support Assistant for the Internship Tracker Platform.
Your job is to answer questions ONLY using the provided knowledge base context.

STRICT RULES:
1. Answer ONLY from the provided context.
2. If the answer is not in the context, respond EXACTLY with:
   "I don't know based on the available knowledge base."
3. Do NOT make up answers, guess requirements, invent deadlines, or assume policies.
4. Be professional, concise, and accurate.
5. Do not reveal internal system details, embeddings, or database internals.
6. Do not expose sensitive user information.
"""

_model = None


def is_greeting_question(question: str) -> bool:
    normalized = " ".join((question or "").strip().lower().split())
    if not normalized:
        return False
    greeting_starts = (
        "hi",
        "hello",
        "hey",
        "good morning",
        "good afternoon",
        "good evening",
    )
    return normalized in {"hi", "hello", "hey"} or normalized.startswith(greeting_starts)


def internship_only_reply() -> str:
    return "I only know about internship-related questions."


def greeting_reply() -> str:
    return "Hello! I can help with internship-related questions."


def looks_like_internship_query(question: str) -> bool:
    normalized = " ".join((question or "").strip().lower().split())
    compact = normalized.replace("-", "").replace(" ", "")
    if not compact:
        return False
    return any(
        token in compact
        for token in (
            "internship",
            "internships",
            "intership",
            "interships",
            "internsh",
            "intern",
        )
    )


def classify_internship_intent(question: str) -> dict:
    """
    Use Gemini to reason about internship-search questions and extract simple filters.

    Falls back to keyword logic if Gemini is unavailable.
    """
    normalized = " ".join((question or "").strip().lower().split())
    if not normalized:
        return {"is_internship_search": False, "remote": False, "part_time": False, "location": None, "next_month": False}

    prompt = f"""Classify the user question for an internship search.

Return ONLY valid JSON with these keys:
{{
  "is_internship_search": true or false,
  "remote": true or false,
  "part_time": true or false,
  "location": string or null,
  "next_month": true or false
}}

Rules:
- Treat questions asking for internships, internship listings, available internships, online internships, remote internships, part-time internships, or internships in a place as internship searches.
- If the user asks something unrelated to internships, set is_internship_search to false.
- location should be a short place name if the user mentions one, otherwise null.

User question: {question}
"""

    try:
        response = get_model().generate_content(prompt)
        raw = (response.text or "").strip()
        import json

        data = json.loads(raw)
        return {
            "is_internship_search": bool(data.get("is_internship_search", False)),
            "remote": bool(data.get("remote", False)),
            "part_time": bool(data.get("part_time", False)),
            "location": data.get("location") or None,
            "next_month": bool(data.get("next_month", False)),
        }
    except Exception:
        # Lightweight fallback for simple keyword cases.
        return {
            "is_internship_search": looks_like_internship_query(normalized),
            "remote": any(token in normalized for token in ("online", "remote", "work from home", "wfh")),
            "part_time": any(token in normalized for token in ("part time", "part-time", "parttime")),
            "location": None,
            "next_month": "next month" in normalized or "coming month" in normalized,
        }


def get_model():
    global _model
    if _model is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set. Set GEMINI_API_KEY in your environment or .env")

        def _mask_key(k: str) -> str:
            if not k or len(k) < 8:
                return "****"
            return f"{k[:4]}...{k[-4:]}"

        try:
            genai.configure(api_key=api_key)
            _model = genai.GenerativeModel(
                model_name="gemini-2.5-flash",
                system_instruction=SYSTEM_PROMPT,
            )
        except Exception as e:
            # Raise a clearer error pointing to the env var while masking the key
            masked = _mask_key(api_key)
            raise ValueError(
                f"Failed to initialize Gemini client using GEMINI_API_KEY (value masked: {masked}). "
                f"Ensure GEMINI_API_KEY is set and valid. Underlying error: {str(e)}"
            )
    return _model


def answer_question(question: str, context_docs: list[dict]) -> str:
    """
    Answer a question using retrieved context documents.
    Returns the answer string.
    """
    if not context_docs:
        return internship_only_reply()

    direct_answer = _direct_process_answer(question, context_docs)
    if direct_answer:
        return direct_answer

    # Build context string from retrieved documents
    context_parts = []
    for i, doc in enumerate(context_docs, 1):
        context_parts.append(
            f"[Document {i}: {doc.get('title', 'Unknown')}]\n{doc.get('content', '')}"
        )
    context = "\n\n---\n\n".join(context_parts)

    prompt = f"""Context from knowledge base:

{context}

---

User Question: {question}

Instructions:
- If the user is greeting you, reply naturally and briefly.
- Answer ONLY from the context above.
- If the answer is not present in the context, say exactly:
    "{internship_only_reply()}"
- Keep the answer concise and accurate.
- Do not infer or fabricate information."""

    model = get_model()
    response = model.generate_content(prompt)
    return response.text.strip()


def _direct_process_answer(question: str, context_docs: list[dict]) -> str | None:
    normalized = " ".join((question or "").strip().lower().split())
    if not normalized:
        return None

    titles = {str(doc.get("title", "")).lower(): doc for doc in context_docs}

    if "logbook" in normalized:
        for title, doc in titles.items():
            if "weekly logbook process" in title:
                return (
                    "Submit your weekly logbook entry through the platform each week. "
                    "The workflow is: DRAFT → SUBMITTED → VERIFIED by the company → REVIEWED by the advisor. "
                    "If a week is rejected, revise it and resubmit it."
                )

    if "evaluation" in normalized or "assess" in normalized or "process" in normalized:
        for title, doc in titles.items():
            if "evaluation workflow" in title:
                return (
                    "After the internship starts, the evaluations happen in this order: company monthly evaluations, "
                    "company final evaluation, advisor evaluation, two examiner evaluations, advisor overall approval, "
                    "then final coordinator approval."
                )

    return None


def generate_recommendation_summary(cv_data: dict, recommendations: list[dict]) -> str:
    """
    Generate a natural language summary of internship recommendations.
    """
    if not recommendations:
        return "No matching internships found in the knowledge base."

    model = get_model()

    rec_text = "\n".join([
        f"- {r['title']} at {r['company']} ({r['matchPercentage']}% match): {r['reason']}"
        for r in recommendations[:5]
    ])

    skills = ", ".join(cv_data.get("skills", [])[:10])

    prompt = f"""Based on the candidate's skills ({skills}), here are the top internship matches:

{rec_text}

Write a brief, professional summary (3-4 sentences) explaining these recommendations.
Focus on why these internships are a good fit. Be encouraging but accurate."""

    response = model.generate_content(prompt)
    return response.text.strip()
