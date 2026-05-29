"""
Knowledge base indexing — converts Django model instances into
searchable vector documents.
"""
from .embeddings import embed_text
from .vector_store import upsert_document, delete_document


# ── Internship Positions ──────────────────────────────────────────────────────

def index_internship(position):
    """Index an InternshipPosition into the knowledge base."""
    skills = list(position.required_skills.values_list("name", flat=True))
    content = (
        f"Internship: {position.title}\n"
        f"Company: {position.company.company_name}\n"
        f"Department: {getattr(position, 'department', '')}\n"
        f"Description: {position.description or ''}\n"
        f"Required Skills: {', '.join(skills)}\n"
        f"Duration: {getattr(position, 'duration', '')}\n"
        f"Status: {getattr(position, 'status', 'OPEN')}\n"
    )
    embedding = embed_text(content)
    upsert_document(
        doc_id=f"internship_{position.id}",
        doc_type="internship",
        title=position.title,
        content=content,
        embedding=embedding,
        metadata={
            "internshipId": position.id,
            "company": position.company.company_name,
            "skills": skills,
            "status": getattr(position, "status", "OPEN"),
        },
    )


def remove_internship(position_id: int):
    delete_document(f"internship_{position_id}")


# ── Process / FAQ Documents ───────────────────────────────────────────────────

PROCESS_DOCUMENTS = [
    {
        "id": "process_application_flow",
        "title": "How the Application Process Works",
        "content": (
            "Students browse available internship positions and submit applications. "
            "Each application goes through the following stages:\n"
            "1. PENDING — submitted, awaiting coordinator review.\n"
            "2. APPROVED (dept_status) — coordinator approved the application.\n"
            "3. OFFER_RECEIVED — company mentor sent an offer.\n"
            "4. ACCEPTED — student accepted the offer.\n"
            "5. DECLINED — student or company declined.\n"
            "The coordinator must approve before the company can make an offer."
        ),
    },
    {
        "id": "process_evaluation_workflow",
        "title": "Evaluation Workflow",
        "content": (
            "After the internship starts, evaluations happen in this order:\n"
            "1. Company submits monthly evaluations (Month 1 and Month 2).\n"
            "2. Company submits a final industry evaluation.\n"
            "3. Advisor submits their university supervisor evaluation.\n"
            "4. Two internal examiners submit their evaluations.\n"
            "5. Advisor approves the overall evaluation.\n"
            "6. Coordinator gives final approval.\n"
            "Students can view results only after coordinator approval."
        ),
    },
    {
        "id": "process_logbook",
        "title": "Weekly Logbook Process",
        "content": (
            "Students submit weekly logbook entries describing their work.\n"
            "Status flow: DRAFT → SUBMITTED → VERIFIED (company) → REVIEWED (advisor approved).\n"
            "The company verifies each week first, then the advisor approves.\n"
            "Rejected weeks must be revised and resubmitted by the student."
        ),
    },
    {
        "id": "process_roles",
        "title": "Platform Roles and Permissions",
        "content": (
            "STUDENT: Apply for internships, submit logbooks, upload documents, view results.\n"
            "COMPANY MENTOR: Post internship positions, review applications, verify logbooks, "
            "submit monthly and final evaluations.\n"
            "ADVISOR: Approve logbooks, submit university evaluation, approve overall evaluation.\n"
            "EXAMINER: Submit examiner evaluation, approve documents.\n"
            "COORDINATOR: Approve applications, assign advisors and examiners, give final approval.\n"
            "ADMIN: Full platform access."
        ),
    },
    {
        "id": "process_documents",
        "title": "Internship Document Submission",
        "content": (
            "Students upload internship documents (reports, certificates, etc.).\n"
            "Documents must be approved by both the advisor and the examiner.\n"
            "Status: PENDING → APPROVED or REJECTED.\n"
            "Both advisor and examiner review independently."
        ),
    },
    {
        "id": "process_self_placement",
        "title": "Self-Placement Requests",
        "content": (
            "Students who have found their own internship host can submit a self-placement request.\n"
            "The coordinator reviews and approves or rejects the request.\n"
            "Approved self-placements are treated the same as platform-matched internships."
        ),
    },
    {
        "id": "faq_status",
        "title": "FAQ: What do the application statuses mean?",
        "content": (
            "PENDING: Your application is waiting for coordinator review.\n"
            "AWAITING_MENTOR: Coordinator approved; waiting for company to respond.\n"
            "OFFER_RECEIVED: Company sent you an offer. You can accept or decline.\n"
            "ACCEPTED: You accepted the offer. Internship will start soon.\n"
            "DECLINED: The application was declined by you or the company.\n"
            "APPROVED: Fully approved and active."
        ),
    },
    {
        "id": "faq_evaluation_scores",
        "title": "FAQ: How are evaluation scores calculated?",
        "content": (
            "The overall internship score is out of 100:\n"
            "- Advisor evaluation: 35 points (Report 20%, Logbook 5%, Performance 10%)\n"
            "- Examiner 1 evaluation: up to 22.5 points\n"
            "- Examiner 2 evaluation: up to 22.5 points\n"
            "- Company monthly evaluations: 20 points (average of Month 1 and Month 2)\n"
            "- Company final evaluation: 20 points\n"
            "Total: 100 points. Grade: A (90+), B (80+), C (70+), D (60+), F (<60)."
        ),
    },
]


def index_all_process_documents():
    """Index all static process/FAQ documents into the knowledge base."""
    for doc in PROCESS_DOCUMENTS:
        embedding = embed_text(doc["content"])
        upsert_document(
            doc_id=doc["id"],
            doc_type="process",
            title=doc["title"],
            content=doc["content"],
            embedding=embedding,
            metadata={"category": "process"},
        )


def index_all_internships():
    """Index all active internship positions from the database."""
    from core.models import InternshipPosition
    positions = InternshipPosition.objects.select_related("company").all()
    for pos in positions:
        try:
            index_internship(pos)
        except Exception as e:
            print(f"Failed to index internship {pos.id}: {e}")
