"""parse_command: free text or voice transcript -> structured outreach request."""

import re
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from nobu.pipeline.core import Deps, audited

SYSTEM = """You turn a job-seeker's outreach command into structured fields.
Extract: company name, role, the company's web domain if stated or obvious from a URL,
a job post URL if given, a contact name/email if given, and any extra notes.
Leave a field "" if not stated. Do not guess domains you are unsure of.
In `uncertain`, list anything that looks mis-heard or ambiguous (e.g. an odd company name
from speech recognition)."""

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


class CommandInput(BaseModel):
    text: str


class ParsedCommand(BaseModel):
    company: str = ""
    role: str = ""
    company_domain: str = ""
    job_url: str = ""
    contact_name: str = ""
    contact_email: str = ""
    notes: str = ""


class ParsedCommandLLM(ParsedCommand):
    uncertain: list[str] = Field(default_factory=list)


class ParseResult(BaseModel):
    parsed: ParsedCommand
    issues: list[str]

    @property
    def ok(self) -> bool:
        return not self.issues


def normalize_domain(value: str) -> str:
    value = value.strip().lower()
    if not value:
        return ""
    host = urlparse(value if "//" in value else f"//{value}").hostname or ""
    return host.removeprefix("www.")


def validate(parsed: ParsedCommand) -> ParseResult:
    """Code-level checks; used both after the LLM and when the user edits the fields."""
    p = parsed.model_copy()
    p.company_domain = normalize_domain(p.company_domain)
    p.contact_email = p.contact_email.strip().lower()
    issues: list[str] = []
    if not p.company.strip():
        issues.append("Which company?")
    if not p.role.strip():
        issues.append("Which role?")
    if p.job_url and not p.job_url.startswith(("http://", "https://")):
        issues.append(f"Job URL {p.job_url!r} is not a web address.")
    if p.contact_email and not EMAIL.match(p.contact_email):
        issues.append(f"Contact email {p.contact_email!r} looks invalid.")
    return ParseResult(parsed=p, issues=issues)


def parse_command(deps: Deps, inp: CommandInput) -> ParseResult:
    def run() -> ParseResult:
        llm_out = deps.llm.complete("parse_command", SYSTEM, inp.text, ParsedCommandLLM)
        result = validate(ParsedCommand(**llm_out.model_dump(exclude={"uncertain"})))
        result.issues.extend(f"Please confirm: {u}" for u in llm_out.uncertain)
        return result

    return audited(deps, "parse_command", inp, run)
