"""Shared deterministic test data: stub LLM responses and a fake company website."""

from typing import Any

RESUME_RESPONSE: dict[str, Any] = {
    "name": "Sahil Sharma",
    "links": {"github": "https://github.com/sahil"},
    "facts": [
        {
            "type": "project",
            "description": "Scouter: a FastAPI service that indexes job posts in Postgres.",
            "tech": ["python", "fastapi", "postgres"],
            "outcome": "Handles 10k posts",
            "links": ["https://github.com/sahil/scouter"],
            "tags": ["backend"],
        },
        {
            "type": "achievement",
            "description": "Won first place at a college hackathon.",
            "tech": [],
            "outcome": "",
            "links": [],
            "tags": [],
        },
        {
            "type": "skill",
            "description": "Languages: Python, TypeScript, SQL.",
            "tech": ["python", "typescript", "sql"],
            "outcome": "",
            "links": [],
            "tags": [],
        },
    ],
}

ACME_PAGES: dict[str, str] = {
    "https://acme.dev": (
        "<title>Acme</title><p>Acme builds developer APIs for payments in India.</p>"
    ),
    "https://acme.dev/about": (
        "<p>We are a 20-person seed-stage team. Our backend is Python and Postgres.</p>"
    ),
    "https://acme.dev/careers": (
        "<p>Backend intern: FastAPI, Postgres. Apply at careers@acme.dev or "
        "write to our CTO priya@acme.dev</p>"
    ),
}

PARSE_RESPONSE: dict[str, Any] = {
    "company": "Acme",
    "role": "backend intern",
    "company_domain": "https://www.acme.dev/",
    "uncertain": [],
}

BRIEF_RESPONSE: dict[str, Any] = {
    "what_they_build": [
        {"text": "Developer APIs for payments in India", "source_url": "https://acme.dev"}
    ],
    "stack_signals": [
        {"text": "Backend is Python and Postgres", "source_url": "https://acme.dev/about"},
        {"text": "Uses Rust", "source_url": "https://made-up.example"},
    ],
    "stage_size": [{"text": "20-person seed stage", "source_url": "https://acme.dev/about"}],
    "recent_news": [],
    "role_needs": [{"text": "FastAPI, Postgres", "source_url": "https://acme.dev/careers"}],
}

MATCH_RESPONSE: dict[str, Any] = {
    "picks": [
        {"fact_id": 1, "rationale": "FastAPI+Postgres matches their stack", "company_point": "x"},
        {"fact_id": 999, "rationale": "invented", "company_point": "x"},
    ]
}

DRAFT_RESPONSE: dict[str, Any] = {
    "subject": "Backend intern: FastAPI + Postgres builder",
    "body": (
        "Hi Priya,\n\nI built Scouter, a FastAPI service on Postgres that handles 10k posts. "
        "Your careers page asks for FastAPI and Postgres for the backend intern role. "
        "Would you be open to a 15-minute chat?"
    ),
    "claims": [
        {"text": "built Scouter handling 10k posts", "kind": "self", "ref": "1"},
        {
            "text": "role asks for FastAPI and Postgres",
            "kind": "company",
            "ref": "https://acme.dev/careers",
        },
    ],
}

CRITIC_OK: dict[str, Any] = {"flags": []}


def stub_responses() -> dict[str, Any]:
    return {
        "extract_resume": RESUME_RESPONSE,
        "parse_command": PARSE_RESPONSE,
        "research_company": BRIEF_RESPONSE,
        "match_facts": MATCH_RESPONSE,
        "draft_email": DRAFT_RESPONSE,
        "critic": CRITIC_OK,
    }
