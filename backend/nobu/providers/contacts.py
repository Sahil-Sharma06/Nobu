"""Contact discovery adapters.

Phase 1 uses only public pages (emails visibly published on the company site or job post).
A paid contact-data provider (Hunter, Apollo, ...) plugs in later behind `ContactProvider`.
"""

import re
from dataclasses import dataclass
from typing import Protocol

from nobu.providers.fetch import Page

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
GENERIC_LOCALPARTS = {"careers", "jobs", "hiring", "hr", "talent", "recruiting", "hello", "contact"}
NEVER_EMAIL = {"noreply", "no-reply", "donotreply", "privacy", "abuse", "legal", "support"}


@dataclass(frozen=True)
class ContactCandidate:
    email: str
    name: str
    title: str
    source: str  # URL or "user"
    confidence: float  # 0..1


class ContactProvider(Protocol):
    def find(self, domain: str, role: str) -> list[ContactCandidate]: ...


def emails_on_pages(pages: list[Page], domain: str) -> list[ContactCandidate]:
    """Emails published on public pages, restricted to the company domain."""
    seen: dict[str, ContactCandidate] = {}
    domain = domain.lower().removeprefix("www.")
    for page in pages:
        for raw in EMAIL_RE.findall(page.text):
            email = raw.lower().rstrip(".")
            local, _, host = email.partition("@")
            if not (host == domain or host.endswith("." + domain)) or local in NEVER_EMAIL:
                continue
            # Published on the company's own page: high confidence it exists.
            # Generic role inboxes are real but less targeted.
            conf = 0.85 if local in GENERIC_LOCALPARTS else 0.9
            seen.setdefault(email, ContactCandidate(email, "", "", page.url, conf))
    return list(seen.values())


class NullContactProvider:
    """Phase 1 default: no paid lookups."""

    def find(self, domain: str, role: str) -> list[ContactCandidate]:
        return []


class FakeContactProvider:
    def __init__(self, by_domain: dict[str, list[ContactCandidate]]) -> None:
        self.by_domain = by_domain

    def find(self, domain: str, role: str) -> list[ContactCandidate]:
        return self.by_domain.get(domain, [])
