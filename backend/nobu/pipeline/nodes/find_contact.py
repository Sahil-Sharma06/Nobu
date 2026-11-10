"""find_contact: choose who to email and how confident we are in the address.

Confidence gates (spec 6.5): >= 0.8 propose normally; 0.5-0.8 the user must confirm;
< 0.5 never proposed.
"""

from pydantic import BaseModel

from nobu.db.models import Contact
from nobu.pipeline.core import Deps, audited
from nobu.pipeline.nodes.research_company import PageModel
from nobu.providers.contacts import GENERIC_LOCALPARTS, ContactCandidate, emails_on_pages
from nobu.providers.fetch import Page

PROPOSE = 0.8
ASK = 0.5


class ContactInput(BaseModel):
    company_id: int
    domain: str
    role: str
    user_contact_name: str = ""
    user_contact_email: str = ""
    pages: list[PageModel] = []


class CandidateModel(BaseModel):
    email: str
    name: str
    title: str
    source: str
    confidence: float


class ContactOutput(BaseModel):
    contact_id: int | None
    chosen: CandidateModel | None
    needs_user_ok: bool
    rationale: str
    candidates: list[CandidateModel]
    sources: list[str]


def _rank(c: ContactCandidate) -> tuple[float, int]:
    personal = 0 if c.email.split("@")[0] in GENERIC_LOCALPARTS else 1
    return (c.confidence, personal)


def find_contact(deps: Deps, inp: ContactInput) -> ContactOutput:
    def run() -> ContactOutput:
        cands: list[ContactCandidate] = []
        if inp.user_contact_email:
            cands.append(
                ContactCandidate(inp.user_contact_email, inp.user_contact_name, "", "user", 1.0)
            )
        pages = [Page(p.url, p.title, p.text) for p in inp.pages]
        cands += emails_on_pages(pages, inp.domain)
        cands += deps.contacts.find(inp.domain, inp.role)

        seen: set[str] = set()
        usable = []
        for c in sorted(cands, key=_rank, reverse=True):
            if c.email not in seen and c.confidence >= ASK:
                seen.add(c.email)
                usable.append(c)
        models = [CandidateModel(**c.__dict__) for c in usable]
        if not usable:
            return ContactOutput(
                contact_id=None,
                chosen=None,
                needs_user_ok=False,
                rationale="No published or provided email with enough confidence. "
                "Add a contact yourself.",
                candidates=[],
                sources=[],
            )

        best = usable[0]
        if best.source == "user":
            why = "You named this contact."
        elif best.email.split("@")[0] in GENERIC_LOCALPARTS:
            why = f"Only a general inbox is published ({best.source}); no named person found."
        else:
            why = (
                f"A named address published on the company's own site ({best.source}); "
                "a direct person beats a general inbox, especially at a small team."
            )
        contact = Contact(
            company_id=inp.company_id,
            name=best.name,
            title=best.title,
            email=best.email,
            source=best.source,
            confidence=best.confidence,
        )
        deps.db.add(contact)
        deps.db.commit()
        return ContactOutput(
            contact_id=contact.id,
            chosen=models[0],
            needs_user_ok=best.confidence < PROPOSE,
            rationale=why,
            candidates=models,
            sources=[best.source] if best.source.startswith("http") else [],
        )

    return audited(deps, "find_contact", inp, run)
