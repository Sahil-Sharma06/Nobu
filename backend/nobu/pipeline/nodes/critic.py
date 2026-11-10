"""critic: deterministic checks in code, then an LLM check of every claim in the body.

Any flag blocks sending until the user resolves it (edits, or explicitly acknowledges it).
"""

from typing import Literal

from pydantic import BaseModel

from nobu.pipeline.core import Deps, audited
from nobu.pipeline.nodes.draft_email import Claim

SYSTEM = """You are a strict reviewer of a cold email written by a job seeker.
Flag ONLY real problems:
- unsupported_self: a statement about the sender not supported by the given facts.
- unsupported_company: a statement about the company not supported by the given brief.
- flattery: empty praise or filler.
- multiple_asks: more than one request.
- invented_number: a number not present in the facts or brief.
Return an empty list if the email is fine. Each message: one short sentence quoting the issue."""

MAX_WORDS = 130


class Flag(BaseModel):
    code: str
    message: str
    source: Literal["code", "llm"] = "code"
    resolved: bool = False


class LLMFlag(BaseModel):
    code: str
    message: str


class CriticLLM(BaseModel):
    flags: list[LLMFlag]


class CriticInput(BaseModel):
    subject: str
    core_body: str
    claims: list[Claim]
    fact_ids: list[int]
    facts: list[dict[str, object]]
    brief_points: list[dict[str, str]]
    source_urls: list[str]
    has_contact: bool
    contact_needs_ok: bool


class CriticOutput(BaseModel):
    flags: list[Flag]


def code_checks(inp: CriticInput) -> list[Flag]:
    flags: list[Flag] = []
    words = len(inp.core_body.split())
    if words > MAX_WORDS:
        flags.append(Flag(code="too_long", message=f"Body is {words} words (max {MAX_WORDS})."))
    if not inp.subject.strip():
        flags.append(Flag(code="no_subject", message="Subject is empty."))
    allowed_facts = {str(i) for i in inp.fact_ids}
    allowed_urls = set(inp.source_urls)
    for c in inp.claims:
        if c.kind == "self" and c.ref not in allowed_facts:
            flags.append(Flag(code="untraced_self", message=f"Claim not in fact bank: {c.text!r}"))
        if c.kind == "company" and c.ref not in allowed_urls:
            flags.append(Flag(code="untraced_company", message=f"Claim has no source: {c.text!r}"))
    if not any(c.kind == "company" for c in inp.claims):
        flags.append(
            Flag(code="no_company_link", message="No specific, sourced point about the company.")
        )
    if not inp.has_contact:
        flags.append(Flag(code="no_contact", message="No recipient email yet."))
    elif inp.contact_needs_ok:
        flags.append(
            Flag(
                code="low_confidence_contact",
                message="Recipient address confidence is below 0.8; confirm it before sending.",
            )
        )
    return flags


def critic(deps: Deps, inp: CriticInput) -> CriticOutput:
    def run() -> CriticOutput:
        flags = code_checks(inp)
        user = (
            f"Subject: {inp.subject}\n\nBody:\n{inp.core_body}\n\n"
            f"Facts about the sender:\n{inp.facts}\n\nCompany brief:\n{inp.brief_points}"
        )
        out = deps.llm.complete("critic", SYSTEM, user, CriticLLM)
        flags += [Flag(code=f.code, message=f.message, source="llm") for f in out.flags]
        return CriticOutput(flags=flags)

    return audited(deps, "critic", inp, run)
