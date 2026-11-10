"""The drafting graph: research -> match -> find contact -> draft -> critic.

The human-in-the-loop interrupt (spec 7.7) is the end of this graph: the result is stored as
an Outreach in state `drafted`, and nothing else happens until the user acts on it through
the review API. The database row is the durable checkpoint, so a server restart never loses
a pending review. Sending is a separate, guarded step (nobu.guardrails.sending).
"""

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from nobu.db.models import AuditStep, Fact, Outreach, Profile
from nobu.pipeline.core import Deps, NodeError
from nobu.pipeline.nodes.critic import CriticInput, CriticOutput, critic
from nobu.pipeline.nodes.draft_email import DraftInput, DraftOutput, draft_email
from nobu.pipeline.nodes.find_contact import ContactInput, ContactOutput, find_contact
from nobu.pipeline.nodes.match_facts import MatchInput, MatchOutput, fact_to_dict, match_facts
from nobu.pipeline.nodes.parse_command import ParsedCommand, validate
from nobu.pipeline.nodes.research_company import ResearchInput as RI
from nobu.pipeline.nodes.research_company import ResearchOutput, research_company


class DraftState(TypedDict, total=False):
    parsed: ParsedCommand
    override_fact_ids: list[int]
    research: ResearchOutput
    match: MatchOutput
    contact: ContactOutput
    draft: DraftOutput
    critic: CriticOutput


def critic_input_for(
    deps: Deps,
    subject: str,
    core_body: str,
    claims: list[Any],
    research_sources: list[str],
    brief_points: list[dict[str, str]],
    picked_ids: list[int],
    has_contact: bool,
    contact_needs_ok: bool,
) -> CriticInput:
    facts = deps.db.query(Fact).filter(Fact.id.in_(picked_ids)).all() if picked_ids else []
    return CriticInput(
        subject=subject,
        core_body=core_body,
        claims=claims,
        fact_ids=[f.id for f in deps.db.query(Fact).all()],
        facts=[fact_to_dict(f) for f in facts],
        brief_points=brief_points,
        source_urls=research_sources,
        has_contact=has_contact,
        contact_needs_ok=contact_needs_ok,
    )


def draft_input_for(
    deps: Deps,
    parsed: ParsedCommand,
    research: ResearchOutput,
    match: MatchOutput,
    contact_name: str,
    instructions: str = "",
) -> DraftInput:
    profile = deps.db.query(Profile).first() or Profile()
    ids = [p.fact_id for p in match.picks]
    facts = deps.db.query(Fact).filter(Fact.id.in_(ids)).all()
    return DraftInput(
        company=parsed.company,
        role=parsed.role,
        brief=research.brief,
        picks=match.picks,
        facts=[fact_to_dict(f) for f in facts],
        contact_name=contact_name,
        sender_name=profile.name,
        sign_off=profile.sign_off,
        tone=profile.tone,
        links={k: str(v) for k, v in (profile.links or {}).items()},
        instructions=instructions,
    )


def build_graph(deps: Deps) -> Any:
    def n_research(s: DraftState) -> DraftState:
        p = s["parsed"]
        inp = RI(company=p.company, role=p.role, domain=p.company_domain, job_url=p.job_url)
        return {"research": research_company(deps, inp)}

    def n_match(s: DraftState) -> DraftState:
        inp = MatchInput(
            role=s["parsed"].role,
            brief=s["research"].brief,
            override_fact_ids=s.get("override_fact_ids", []),
        )
        return {"match": match_facts(deps, inp)}

    def n_contact(s: DraftState) -> DraftState:
        p, r = s["parsed"], s["research"]
        inp = ContactInput(
            company_id=r.company_id,
            domain=r.domain,
            role=p.role,
            user_contact_name=p.contact_name,
            user_contact_email=p.contact_email,
            pages=r.pages,
        )
        return {"contact": find_contact(deps, inp)}

    def n_draft(s: DraftState) -> DraftState:
        c = s["contact"]
        name = c.chosen.name if c.chosen else ""
        inp = draft_input_for(deps, s["parsed"], s["research"], s["match"], name)
        return {"draft": draft_email(deps, inp)}

    def n_critic(s: DraftState) -> DraftState:
        d, r, c = s["draft"], s["research"], s["contact"]
        inp = critic_input_for(
            deps,
            d.subject,
            d.core_body,
            d.claims,
            r.sources,
            [p.model_dump() for p in r.brief.points()],
            [p.fact_id for p in s["match"].picks],
            c.chosen is not None,
            c.needs_user_ok,
        )
        return {"critic": critic(deps, inp)}

    g: Any = StateGraph(DraftState)  # langgraph overloads reject plain TypedDict fns
    g.add_node("research_company", n_research)
    g.add_node("match_facts", n_match)
    g.add_node("find_contact", n_contact)
    g.add_node("draft_email", n_draft)
    g.add_node("critic", n_critic)
    g.add_edge(START, "research_company")
    g.add_edge("research_company", "match_facts")
    g.add_edge("match_facts", "find_contact")
    g.add_edge("find_contact", "draft_email")
    g.add_edge("draft_email", "critic")
    g.add_edge("critic", END)
    return g.compile()


def run_drafting(
    deps: Deps, parsed: ParsedCommand, override_fact_ids: list[int] | None = None
) -> Outreach:
    """Run the graph for a confirmed request and store the result as a drafted Outreach."""
    checked = validate(parsed)
    if not checked.ok:
        raise NodeError(" ".join(checked.issues))
    s: DraftState = build_graph(deps).invoke(
        {"parsed": checked.parsed, "override_fact_ids": override_fact_ids or []}
    )
    d, r, c, m = s["draft"], s["research"], s["contact"], s["match"]
    outreach = Outreach(
        company_id=r.company_id,
        contact_id=c.contact_id,
        role=checked.parsed.role,
        subject=d.subject,
        body=d.body,
        highlighted_fact_ids=[p.fact_id for p in m.picks],
        critic_flags=[f.model_dump() for f in s["critic"].flags],
        rationale={
            "request": checked.parsed.model_dump(),
            "picks": [p.model_dump() for p in m.picks],
            "contact": c.model_dump(exclude={"sources"}),
            "claims": [cl.model_dump() for cl in d.claims],
            "core_body": d.core_body,
            "footer": d.body[len(d.core_body) :],
            "brief": r.brief.model_dump(),
            "sources": r.sources,
            "run_id": deps.run_id,
        },
    )
    deps.db.add(outreach)
    deps.db.flush()
    deps.db.query(AuditStep).filter_by(run_id=deps.run_id).update({"outreach_id": outreach.id})
    deps.db.commit()
    return outreach
