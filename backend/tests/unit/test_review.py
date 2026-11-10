import pytest

from nobu.db.models import AuditStep, OutreachState
from nobu.llm.stub import StubLLM
from nobu.pipeline import review
from nobu.pipeline.core import Deps, NodeError
from nobu.pipeline.graph import run_drafting
from nobu.pipeline.nodes.parse_command import ParsedCommand

REQ = ParsedCommand(company="Acme", role="backend intern", company_domain="acme.dev")


def test_run_drafting_produces_clean_draft_and_links_audit(with_resume: Deps) -> None:
    o = run_drafting(with_resume, REQ)
    assert o.state is OutreachState.drafted
    assert o.critic_flags == []
    assert o.highlighted_fact_ids == [1]
    assert o.rationale["contact"]["chosen"]["email"] == "priya@acme.dev"
    nodes = [
        a.node for a in with_resume.db.query(AuditStep).filter_by(outreach_id=o.id).order_by("id")
    ]
    assert nodes == ["research_company", "match_facts", "find_contact", "draft_email", "critic"]


def test_run_drafting_rejects_unconfirmed_request(with_resume: Deps) -> None:
    with pytest.raises(NodeError):
        run_drafting(with_resume, ParsedCommand(company="Acme", role=""))


def test_edit_reruns_critic_and_unapproves(with_resume: Deps) -> None:
    o = run_drafting(with_resume, REQ)
    review.approve(with_resume, o)
    review.edit(with_resume, o, o.subject, "word " * 200 + o.rationale["footer"])
    assert o.state is OutreachState.drafted
    assert [f["code"] for f in o.critic_flags] == ["too_long"]
    with pytest.raises(NodeError):
        review.approve(with_resume, o)
    review.resolve_flag(with_resume, o, 0)
    review.approve(with_resume, o)
    assert o.state.value == "approved"


def test_regenerate_passes_instructions(with_resume: Deps) -> None:
    o = run_drafting(with_resume, REQ)
    review.regenerate(with_resume, o, "mention my hackathon win")
    assert isinstance(with_resume.llm, StubLLM)
    assert any("hackathon win" in c[2] for c in with_resume.llm.calls if c[0] == "draft_email")


def test_no_contact_flag_needs_a_recipient(with_resume: Deps) -> None:
    from tests.fixtures import ACME_PAGES

    pages = dict(ACME_PAGES)
    pages["https://acme.dev/careers"] = "<p>Backend intern: FastAPI, Postgres.</p>"
    with_resume.fetcher = type(with_resume.fetcher)(pages)  # type: ignore[call-arg]
    o = run_drafting(with_resume, REQ)
    assert [f["code"] for f in o.critic_flags] == ["no_contact"]
    with pytest.raises(NodeError):
        review.resolve_flag(with_resume, o, 0)
    review.set_contact(with_resume, o, "Priya@Acme.dev", "Priya")
    assert o.critic_flags == []
    review.approve(with_resume, o)


def test_discard_is_final(with_resume: Deps) -> None:
    o = run_drafting(with_resume, REQ)
    review.discard(with_resume, o)
    with pytest.raises(NodeError):
        review.edit(with_resume, o, "s", "b")
