"""
CV parsing and skill extraction using Gemini 2.5 Flash.
"""
import json
import os
import re

import google.generativeai as genai

SKILL_NORMALIZATIONS = {
    "js": "JavaScript",
    "javascript": "JavaScript",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    "reactjs": "React",
    "react.js": "React",
    "react js": "React",
    "nodejs": "Node.js",
    "node": "Node.js",
    "node js": "Node.js",
    "expressjs": "Express",
    "express.js": "Express",
    "mongodb": "MongoDB",
    "mongo": "MongoDB",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "py": "Python",
    "python3": "Python",
    "django": "Django",
    "drf": "Django REST Framework",
    "rest": "REST APIs",
    "restapi": "REST APIs",
    "rest api": "REST APIs",
    "graphql": "GraphQL",
    "docker": "Docker",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
    "aws": "AWS",
    "gcp": "Google Cloud",
    "azure": "Microsoft Azure",
    "git": "Git",
    "github": "GitHub",
    "ci/cd": "CI/CD",
    "ml": "Machine Learning",
    "ai": "Artificial Intelligence",
    "nlp": "NLP",
    "cv": "Computer Vision",
    "tf": "TensorFlow",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
    "java": "Java",
    "c++": "C++",
    "cpp": "C++",
    "c#": "C#",
    "csharp": "C#",
    "php": "PHP",
    "laravel": "Laravel",
    "vue": "Vue.js",
    "vuejs": "Vue.js",
    "angular": "Angular",
    "flutter": "Flutter",
    "dart": "Dart",
    "swift": "Swift",
    "kotlin": "Kotlin",
    "android": "Android",
    "ios": "iOS",
    "html": "HTML",
    "css": "CSS",
    "sass": "SASS",
    "tailwind": "Tailwind CSS",
    "bootstrap": "Bootstrap",
    "figma": "Figma",
    "ui/ux": "UI/UX Design",
    "sql": "SQL",
    "nosql": "NoSQL",
    "redis": "Redis",
    "elasticsearch": "Elasticsearch",
    "kafka": "Apache Kafka",
    "rabbitmq": "RabbitMQ",
    "nginx": "Nginx",
    "linux": "Linux",
    "bash": "Bash/Shell",
    "shell": "Bash/Shell",
}


def normalize_skill(skill: str) -> str:
    key = skill.strip().lower()
    return SKILL_NORMALIZATIONS.get(key, skill.strip().title())


def get_gemini_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set. Set GEMINI_API_KEY in your environment or .env")

    def _mask_key(k: str) -> str:
        if not k or len(k) < 8:
            return "****"
        return f"{k[:4]}...{k[-4:]}"

    try:
        genai.configure(api_key=api_key)
        return genai.GenerativeModel("gemini-2.5-flash")
    except Exception as e:
        masked = _mask_key(api_key)
        raise ValueError(f"Failed to initialize Gemini client using GEMINI_API_KEY (value masked: {masked}). Ensure GEMINI_API_KEY is set and valid. Underlying error: {e}")


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF bytes using pypdf."""
    try:
        import io
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as e:
        raise ValueError(f"Failed to extract PDF text: {e}")


def parse_cv(cv_text: str) -> dict:
    """
    Use Gemini to extract structured information from CV text.
    Returns normalized JSON with skills, education, experience, etc.
    """
    model = get_gemini_client()

    prompt = f"""Analyze the following CV text and extract structured information.

Return ONLY valid JSON with this exact structure:
{{
  "name": "candidate name or empty string",
  "email": "email or empty string",
  "phone": "phone or empty string",
  "education": [
    {{"degree": "...", "field": "...", "institution": "...", "year": "..."}}
  ],
  "experience": [
    {{"title": "...", "company": "...", "duration": "...", "description": "..."}}
  ],
  "skills": ["skill1", "skill2", ...],
  "technologies": ["tech1", "tech2", ...],
  "certifications": ["cert1", ...],
  "projects": [
    {{"name": "...", "description": "...", "technologies": ["..."]}}
  ],
  "languages": ["language1", ...]
}}

CV Text:
{cv_text[:4000]}

Return ONLY the JSON object, no markdown, no explanation."""

    response = model.generate_content(prompt)
    raw = response.text.strip()

    # Strip markdown code blocks if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON from response
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            data = {"skills": [], "technologies": [], "education": [], "experience": []}

    # Normalize all skills
    all_skills = list(set(
        [normalize_skill(s) for s in data.get("skills", [])] +
        [normalize_skill(s) for s in data.get("technologies", [])]
    ))
    data["skills"] = all_skills
    data["technologies"] = all_skills

    return data
