"""Review actions on a drafted outreach: edit, regenerate, resolve flags, set contact,
approve, discard. Every state change goes through the state machine."""

from typing import Any

from nobu.db.models import Actor, Contact, Outreach
from nobu.db.models import OutreachState as S
from nobu.guardrails.send_policy import unresolved_flags
from nobu.guardrails.state_machine import transition
from nobu.pipeline.core import Deps, NodeError
from nobu.pipeline.graph import critic_input_for, draft_input_for
from nobu.pipeline.nodes.critic import critic
from nobu.pipeline.nodes.draft_email import Claim, draft_email
from nobu.pipeline.nodes.find_contact import PROPOSE
from nobu.pipeline.nodes.match_facts import MatchOutput, Pick
from nobu.pipeline.nodes.parse_command import ParsedCommand
from nobu.pipeline.nodes.research_company import CompanyBrief, ResearchOutput

EDITABLE = {S.drafted, S.approved}


def _require_editable(o: Outreach) -> None:
    if o.state not in EDITABLE:
        raise NodeError(f"This outreach is {o.state.value} and can no longer be changed.")


def _unapprove(deps: Deps, o: Outreach, why: str) -> None:
    if o.state is S.approved:
        transition(deps.db, o, S.drafted, Actor.user, {"reason": why})


def _contact(deps: Deps, o: Outreach) -> Contact | None:
    return deps.db.get(Contact, o.contact_id) if o.contact_id else None


def _recritic(deps: Deps, o: Outreach) -> None:
    r = o.rationale
    contact = _contact(deps, o)
    footer = r.get("footer", "")
    core = o.body[: -len(footer)] if footer and o.body.endswith(footer) else o.body
    brief = CompanyBrief.model_validate(r["brief"])
    inp = critic_input_for(
        deps,
        o.subject,
        core,
        [Claim.model_validate(c) for c in r.get("claims", [])],
        r.get("sources", []),
        [p.model_dump() for p in brief.points()],
        list(o.highlighted_fact_ids),
        contact is not None,
        contact is not None and contact.confidence < PROPOSE,
    )
    o.critic_flags = [f.model_dump() for f in critic(deps, inp).flags]


def edit(deps: Deps, o: Outreach, subject: str, body: str) -> None:
    _require_editable(o)
    o.subject, o.body = subject, body
    _unapprove(deps, o, "edited")
    _recritic(deps, o)
    deps.db.commit()


def regenerate(deps: Deps, o: Outreach, instructions: str = "") -> None:
    _require_editable(o)
    r = o.rationale
    parsed = ParsedCommand.model_validate(r["request"])
    research = ResearchOutput(
        company_id=o.company_id or 0,
        domain="",
        brief=CompanyBrief.model_validate(r["brief"]),
        sources=r["sources"],
        pages=[],
    )
    match = MatchOutput(picks=[Pick.model_validate(p) for p in r["picks"]])
    contact = _contact(deps, o)
    d = draft_email(
        deps,
        draft_input_for(
            deps, parsed, research, match, contact.name if contact else "", instructions
        ),
    )
    o.subject, o.body = d.subject, d.body
    o.rationale = {
        **r,
        "claims": [c.model_dump() for c in d.claims],
        "core_body": d.core_body,
        "footer": d.body[len(d.core_body) :],
    }
    _unapprove(deps, o, "regenerated")
    _recritic(deps, o)
    deps.db.commit()


def resolve_flag(deps: Deps, o: Outreach, index: int) -> None:
    """The user explicitly acknowledges a flag (e.g. 'yes, that address is right')."""
    _require_editable(o)
    flags: list[dict[str, Any]] = [dict(f) for f in o.critic_flags]
    if not 0 <= index < len(flags):
        raise NodeError("No such flag.")
    if flags[index]["code"] == "no_contact":
        raise NodeError("Add a recipient instead of dismissing this flag.")
    flags[index]["resolved"] = True
    o.critic_flags = flags
    deps.db.commit()


def set_contact(deps: Deps, o: Outreach, email: str, name: str = "") -> None:
    """User-supplied recipient: full confidence, replaces the agent's choice."""
    _require_editable(o)
    if o.company_id is None:
        raise NodeError("Outreach has no company.")
    c = Contact(
        company_id=o.company_id,
        email=email.strip().lower(),
        name=name,
        source="user",
        confidence=1.0,
    )
    deps.db.add(c)
    deps.db.flush()
    o.contact_id = c.id
    o.critic_flags = [
        f for f in o.critic_flags if f["code"] not in {"no_contact", "low_confidence_contact"}
    ]
    _unapprove(deps, o, "contact changed")
    deps.db.commit()


def approve(deps: Deps, o: Outreach) -> None:
    flags = unresolved_flags(o)
    if flags:
        raise NodeError(f"Resolve {len(flags)} critic flag(s) before approving.")
    if o.contact_id is None:
        raise NodeError("Add a recipient before approving.")
    transition(deps.db, o, S.approved, Actor.user)
    deps.db.commit()


def discard(deps: Deps, o: Outreach) -> None:
    transition(deps.db, o, S.discarded, Actor.user)
    deps.db.commit()
