"""
Skill-based internship matching with weighted scoring.
"""
from .embeddings import embed_query
from .vector_store import vector_search


WEIGHTS = {
    "skills": 0.50,
    "experience": 0.25,
    "education": 0.15,
    "certifications": 0.10,
}


def _skill_overlap(candidate_skills: list[str], required_skills: list[str]) -> tuple[list, list]:
    """Return (matching_skills, missing_skills)."""
    norm = lambda s: s.strip().lower()
    candidate_set = {norm(s) for s in candidate_skills}
    matching = [s for s in required_skills if norm(s) in candidate_set]
    missing = [s for s in required_skills if norm(s) not in candidate_set]
    return matching, missing


def match_internships(cv_data: dict, top_k: int = 5) -> list[dict]:
    """
    Match a parsed CV against internship knowledge base documents.
    Returns ranked list of internship recommendations.
    """
    candidate_skills = cv_data.get("skills", []) + cv_data.get("technologies", [])
    candidate_skills = list(set(candidate_skills))

    # Build a rich query from the CV
    query_parts = []
    if candidate_skills:
        query_parts.append(f"Skills: {', '.join(candidate_skills[:20])}")
    for edu in cv_data.get("education", [])[:2]:
        query_parts.append(f"Education: {edu.get('degree', '')} in {edu.get('field', '')}")
    for exp in cv_data.get("experience", [])[:2]:
        query_parts.append(f"Experience: {exp.get('title', '')} at {exp.get('company', '')}")

    query_text = "\n".join(query_parts) or "internship candidate"
    query_embedding = embed_query(query_text)

    # Retrieve top internship documents
    results = vector_search(query_embedding, top_k=top_k * 2, filter_type="internship")

    recommendations = []
    for doc in results:
        meta = doc.get("metadata", {})
        required_skills = meta.get("skills", [])
        vector_score = doc.get("score", 0.0)

        matching, missing = _skill_overlap(candidate_skills, required_skills)

        # Skill match ratio
        if required_skills:
            skill_ratio = len(matching) / len(required_skills)
        else:
            skill_ratio = 0.5  # no requirements = neutral

        # Combine vector similarity with skill overlap
        combined_score = (vector_score * 0.5) + (skill_ratio * 0.5)
        match_pct = round(combined_score * 100, 1)

        recommendations.append({
            "title": doc.get("title", ""),
            "company": meta.get("company", ""),
            "internshipId": meta.get("internshipId"),
            "matchPercentage": match_pct,
            "matchingSkills": matching,
            "missingSkills": missing[:5],
            "reason": _build_reason(doc, matching, missing, cv_data),
            "vectorScore": round(vector_score, 3),
        })

    # Sort by match percentage descending
    recommendations.sort(key=lambda x: x["matchPercentage"], reverse=True)
    return recommendations[:top_k]


def _build_reason(doc: dict, matching: list, missing: list, cv_data: dict) -> str:
    title = doc.get("title", "this internship")
    company = doc.get("metadata", {}).get("company", "the company")
    parts = []

    if matching:
        parts.append(f"You match {len(matching)} required skill(s): {', '.join(matching[:4])}.")
    else:
        parts.append(f"Your profile is semantically similar to {title} at {company}.")

    if missing:
        parts.append(f"You could strengthen your profile by learning: {', '.join(missing[:3])}.")

    edu = cv_data.get("education", [])
    if edu:
        field = edu[0].get("field", "")
        if field:
            parts.append(f"Your {field} background is relevant.")

    return " ".join(parts)
