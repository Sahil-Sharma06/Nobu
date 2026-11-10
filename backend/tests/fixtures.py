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
