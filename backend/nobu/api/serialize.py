"""The review card: everything the UI shows for one outreach."""

from typing import Any

from nobu.db.models import Company, Contact, Event, Fact, Outreach, Profile
from nobu.guardrails import send_policy
from nobu.pipeline.core import Deps


def outreach_card(deps: Deps, o: Outreach, brief: bool = False) -> dict[str, Any]:
    db = deps.db
    company = db.get(Company, o.company_id) if o.company_id else None
    contact = db.get(Contact, o.contact_id) if o.contact_id else None
    card: dict[str, Any] = {
        "id": o.id,
        "state": o.state.value,
        "role": o.role,
        "company": {"name": company.name, "domain": company.domain} if company else None,
        "contact": (
            {
                "email": contact.email,
                "name": contact.name,
                "title": contact.title,
                "confidence": contact.confidence,
                "source": contact.source,
            }
            if contact
            else None
        ),
        "subject": o.subject,
        "created_at": o.created_at.isoformat(),
        "sent_at": o.sent_at.isoformat() if o.sent_at else None,
        "unresolved_flags": len(send_policy.unresolved_flags(o)),
    }
    if brief:
        return card

    r = o.rationale
    picks = {p["fact_id"]: p for p in r.get("picks", [])}
    facts = db.query(Fact).filter(Fact.id.in_(list(picks))).all() if picks else []
    profile = db.query(Profile).first()
    profile_cap = profile.daily_cap if profile else deps.settings.daily_cap
    send_problems = send_policy.check(
        db, o, daily_cap=profile_cap, dedupe_days=deps.settings.dedupe_days
    )
    card.update(
        {
            "body": o.body,
            "flags": [{"index": i, **f} for i, f in enumerate(o.critic_flags)],
            "highlighted": [
                {
                    "fact_id": f.id,
                    "description": f.description,
                    "rationale": picks[f.id]["rationale"],
                    "company_point": picks[f.id]["company_point"],
                }
                for f in facts
            ],
            "contact_rationale": r.get("contact", {}).get("rationale", ""),
            "contact_candidates": r.get("contact", {}).get("candidates", []),
            "claims": r.get("claims", []),
            "brief": r.get("brief", {}),
            "sources": r.get("sources", []),
            "send_problems": send_problems,
            "dry_run": deps.settings.dry_run,
            "events": [
                {"type": e.type, "actor": e.actor.value, "at": e.created_at.isoformat()}
                for e in db.query(Event).filter_by(outreach_id=o.id).order_by(Event.id)
            ],
        }
    )
    return card
