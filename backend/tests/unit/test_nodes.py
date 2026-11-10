from typing import Any

import pytest
from sqlalchemy.orm import Session

from nobu.db.models import AuditStep, Company, Contact
from nobu.llm.stub import StubLLM
from nobu.pipeline.core import Deps, NodeError
from nobu.pipeline.nodes.critic import CriticInput, code_checks, critic
from nobu.pipeline.nodes.draft_email import OPT_OUT, Claim, DraftInput, draft_email
from nobu.pipeline.nodes.find_contact import ContactInput, find_contact
from nobu.pipeline.nodes.match_facts import MatchInput, match_facts
from nobu.pipeline.nodes.parse_command import (
    CommandInput,
    ParsedCommand,
    parse_command,
    validate,
)
from nobu.pipeline.nodes.research_company import (
    CompanyBrief,
    PageModel,
    ResearchInput,
    research_company,
)
from nobu.providers.search import FakeSearch, SearchResult
from tests.fixtures import BRIEF_RESPONSE


def stub(deps: Deps) -> StubLLM:
    assert isinstance(deps.llm, StubLLM)
    return deps.llm


def audit_nodes(db: Session) -> list[str]:
    return [a.node for a in db.query(AuditStep).order_by(AuditStep.id)]


# parse_command


def test_parse_normalizes_domain_and_audits(deps: Deps) -> None:
    r = parse_command(deps, CommandInput(text="reach out to acme for backend intern"))
    assert r.ok
    assert r.parsed.company_domain == "acme.dev"
    assert audit_nodes(deps.db) == ["parse_command"]


def test_parse_flags_missing_and_uncertain(deps: Deps) -> None:
    stub(deps).set("parse_command", {"company": "Akmi", "role": "", "uncertain": ["Akmi?"]})
    r = parse_command(deps, CommandInput(text="reach out to akmi"))
    assert not r.ok
    assert "Which role?" in r.issues
    assert any("Akmi?" in i for i in r.issues)


def test_validate_rejects_bad_email_and_url() -> None:
    r = validate(ParsedCommand(company="A", role="B", contact_email="nope", job_url="acme.dev/job"))
    assert len(r.issues) == 2


# research_company


def test_research_drops_unsourced_points_and_persists(deps: Deps) -> None:
    out = research_company(deps, ResearchInput(company="Acme", role="intern", domain="acme.dev"))
    texts = [p.text for p in out.brief.points()]
    assert "Uses Rust" not in texts  # cited a URL that was never fetched
    assert "Backend is Python and Postgres" in texts
    assert set(out.sources) == {
        "https://acme.dev",
        "https://acme.dev/about",
        "https://acme.dev/careers",
    }
    company = deps.db.query(Company).one()
    assert company.domain == "acme.dev" and company.fetched_at is not None
    assert deps.db.query(AuditStep).one().sources == out.sources


def test_research_finds_domain_via_search(deps: Deps) -> None:
    deps.search = FakeSearch({"official": [SearchResult("Acme", "https://www.acme.dev/x", "")]})
    out = research_company(deps, ResearchInput(company="Acme", role="intern"))
    assert out.domain == "acme.dev"


def test_research_fails_cleanly_when_nothing_fetched(deps: Deps) -> None:
    with pytest.raises(NodeError):
        research_company(deps, ResearchInput(company="X", role="r", domain="nothing.dev"))
    step = deps.db.query(AuditStep).one()
    assert step.error and "NodeError" in step.error


# match_facts


BRIEF = CompanyBrief.model_validate(BRIEF_RESPONSE)


def test_match_drops_invented_fact_ids(with_resume: Deps) -> None:
    out = match_facts(with_resume, MatchInput(role="intern", brief=BRIEF))
    assert [p.fact_id for p in out.picks] == [1]


def test_match_override_and_empty_bank(with_resume: Deps, deps: Deps) -> None:
    out = match_facts(with_resume, MatchInput(role="r", brief=BRIEF, override_fact_ids=[2]))
    assert out.picks[0].fact_id == 2
    with pytest.raises(NodeError):
        match_facts(with_resume, MatchInput(role="r", brief=BRIEF, override_fact_ids=[42]))


def test_match_requires_facts(deps: Deps) -> None:
    with pytest.raises(NodeError, match="empty"):
        match_facts(deps, MatchInput(role="r", brief=BRIEF))


# find_contact


def _company(db: Session) -> int:
    c = Company(name="Acme", domain="acme.dev")
    db.add(c)
    db.commit()
    return c.id


CAREERS = PageModel(
    url="https://acme.dev/careers",
    title="",
    text="Apply at careers@acme.dev or write to priya@acme.dev",
)


def test_contact_prefers_named_person_on_company_page(deps: Deps) -> None:
    out = find_contact(
        deps,
        ContactInput(company_id=_company(deps.db), domain="acme.dev", role="r", pages=[CAREERS]),
    )
    assert out.chosen and out.chosen.email == "priya@acme.dev"
    assert not out.needs_user_ok
    assert out.sources == ["https://acme.dev/careers"]
    assert deps.db.query(Contact).one().confidence == pytest.approx(0.9)


def test_contact_user_supplied_wins(deps: Deps) -> None:
    out = find_contact(
        deps,
        ContactInput(
            company_id=_company(deps.db),
            domain="acme.dev",
            role="r",
            user_contact_email="cto@acme.dev",
            pages=[CAREERS],
        ),
    )
    assert out.chosen and out.chosen.source == "user"


def test_contact_none_found(deps: Deps) -> None:
    out = find_contact(deps, ContactInput(company_id=_company(deps.db), domain="a.dev", role="r"))
    assert out.contact_id is None and out.chosen is None


def test_contact_confidence_gates(deps: Deps) -> None:
    from nobu.providers.contacts import ContactCandidate, FakeContactProvider

    deps.contacts = FakeContactProvider(
        {
            "acme.dev": [
                ContactCandidate("guess@acme.dev", "G", "", "provider", 0.6),
                ContactCandidate("bad@acme.dev", "B", "", "provider", 0.3),
            ]
        }
    )
    out = find_contact(
        deps, ContactInput(company_id=_company(deps.db), domain="acme.dev", role="r")
    )
    assert out.chosen and out.chosen.email == "guess@acme.dev"
    assert out.needs_user_ok  # 0.5-0.8 must be confirmed
    assert all(c.email != "bad@acme.dev" for c in out.candidates)  # < 0.5 skipped


# draft_email


def _draft_input(**kw: Any) -> DraftInput:
    base: dict[str, Any] = {
        "company": "Acme",
        "role": "backend intern",
        "brief": BRIEF,
        "picks": [],
        "facts": [],
        "sender_name": "Sahil",
        "links": {"github": "https://github.com/sahil"},
    }
    return DraftInput(**{**base, **kw})


def test_draft_appends_signoff_links_and_opt_out(deps: Deps) -> None:
    out = draft_email(deps, _draft_input())
    assert out.body.startswith(out.core_body)
    assert "Github: https://github.com/sahil" in out.body
    assert out.body.endswith(OPT_OUT)
    assert "Thanks,\nSahil" in out.body


def test_draft_passes_user_instructions(deps: Deps) -> None:
    draft_email(deps, _draft_input(instructions="make it shorter"))
    assert "make it shorter" in stub(deps).calls[-1][2]


# critic


def _critic_input(**kw: Any) -> CriticInput:
    base: dict[str, Any] = {
        "subject": "Hi",
        "core_body": "short body",
        "claims": [
            Claim(text="a", kind="self", ref="1"),
            Claim(text="b", kind="company", ref="https://acme.dev"),
        ],
        "fact_ids": [1],
        "facts": [],
        "brief_points": [],
        "source_urls": ["https://acme.dev"],
        "has_contact": True,
        "contact_needs_ok": False,
    }
    return CriticInput(**{**base, **kw})


def test_critic_clean_draft_has_no_flags(deps: Deps) -> None:
    assert critic(deps, _critic_input()).flags == []


def test_critic_flags_untraced_claims_length_and_contact() -> None:
    codes = {
        f.code
        for f in code_checks(
            _critic_input(
                core_body="word " * 200,
                claims=[
                    Claim(text="won ICPC", kind="self", ref="77"),
                    Claim(text="raised $10M", kind="company", ref="https://news.fake"),
                ],
                has_contact=False,
            )
        )
    }
    assert codes == {"too_long", "untraced_self", "untraced_company", "no_contact"}


def test_critic_flags_low_confidence_and_missing_company_link() -> None:
    codes = {
        f.code
        for f in code_checks(
            _critic_input(claims=[Claim(text="a", kind="self", ref="1")], contact_needs_ok=True)
        )
    }
    assert codes == {"no_company_link", "low_confidence_contact"}


def test_critic_merges_llm_flags(deps: Deps) -> None:
    stub(deps).set("critic", {"flags": [{"code": "flattery", "message": "huge fan"}]})
    flags = critic(deps, _critic_input()).flags
    assert [(f.code, f.source, f.resolved) for f in flags] == [("flattery", "llm", False)]
