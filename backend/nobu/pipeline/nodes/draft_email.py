"""draft_email: subject + body, with every factual claim tagged to a fact id or source URL.

The sign-off, links and opt-out line are appended in code, so they are always present and
never counted against the word limit.
"""

from typing import Literal

from pydantic import BaseModel

from nobu.pipeline.core import Deps, audited
from nobu.pipeline.nodes.match_facts import Pick
from nobu.pipeline.nodes.research_company import CompanyBrief

SYSTEM = """You write a short cold email from a fresher to someone at a company, about a role.
Hard rules:
- Body under 110 words. No greeting fluff, no flattery ("I'm a huge fan..."), no buzzwords.
- One concrete link between ONE of the given facts and ONE thing the company does or needs.
- One clear ask (e.g. a 15-minute chat, or whether they'd consider them for the role).
- Only state things about the sender that are in the given facts. Never invent numbers.
- Only state things about the company that are in the brief.
- Start with "Hi <first name>," if a contact name is given, else "Hi,". Do NOT add a sign-off,
  name or links at the end; those are added automatically.
- Subject: specific, under 9 words, mentions the role or the concrete link.
List every factual claim you made in `claims`: kind "self" with ref = the fact_id, or kind
"company" with ref = the exact source_url from the brief."""

OPT_OUT = "If you'd rather I didn't follow up, just say so and I won't."


class Claim(BaseModel):
    text: str
    kind: Literal["self", "company"]
    ref: str


class DraftLLM(BaseModel):
    subject: str
    body: str
    claims: list[Claim]


class DraftInput(BaseModel):
    company: str
    role: str
    brief: CompanyBrief
    picks: list[Pick]
    facts: list[dict[str, object]]
    contact_name: str = ""
    sender_name: str = ""
    sign_off: str = ""
    tone: str = ""
    links: dict[str, str] = {}
    instructions: str = ""


class DraftOutput(BaseModel):
    subject: str
    core_body: str
    body: str
    claims: list[Claim]


def compose_body(core: str, inp: DraftInput) -> str:
    closing = inp.sign_off.strip() or f"Thanks,\n{inp.sender_name}".strip()
    link_lines = "\n".join(f"{k.capitalize()}: {v}" for k, v in inp.links.items() if v)
    parts = [core.strip(), closing]
    if link_lines:
        parts.append(link_lines)
    parts.append(OPT_OUT)
    return "\n\n".join(parts)


def draft_email(deps: Deps, inp: DraftInput) -> DraftOutput:
    def run() -> DraftOutput:
        user = (
            f"Company: {inp.company}\nRole: {inp.role}\n"
            f"Contact name: {inp.contact_name or '(unknown)'}\nTone: {inp.tone}\n\n"
            f"Brief:\n{inp.brief.model_dump_json(indent=1)}\n\n"
            f"Chosen facts and why:\n"
            + "\n".join(f"- fact_id {p.fact_id}: {p.rationale}" for p in inp.picks)
            + f"\n\nFact details:\n{inp.facts}"
        )
        if inp.instructions:
            user += f"\n\nThe user asked for this change: {inp.instructions}"
        d = deps.llm.complete("draft_email", SYSTEM, user, DraftLLM)
        return DraftOutput(
            subject=d.subject.strip(),
            core_body=d.body.strip(),
            body=compose_body(d.body, inp),
            claims=d.claims,
        )

    return audited(deps, "draft_email", inp, run)
