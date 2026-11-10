"""Hard send rules, enforced in code (spec 11): state, critic flags, recipient, suppression,
daily cap and dedupe window. `check` returns every violated rule; an empty list means OK."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from nobu.db.models import Contact, Outreach, OutreachState, Suppression

SENT_STATES = {
    OutreachState.sent,
    OutreachState.replied,
    OutreachState.bounced,
    OutreachState.followup_1_due,
    OutreachState.followup_1_sent,
    OutreachState.followup_2_due,
    OutreachState.followup_2_sent,
    OutreachState.closed,
}


def unresolved_flags(outreach: Outreach) -> list[dict[str, object]]:
    return [f for f in outreach.critic_flags if not f.get("resolved")]


def is_suppressed(db: Session, email: str) -> bool:
    email = email.lower()
    domain = email.split("@")[-1]
    return db.query(Suppression).filter(Suppression.value.in_([email, domain])).first() is not None


def check(
    db: Session,
    outreach: Outreach,
    *,
    daily_cap: int,
    dedupe_days: int,
    now: datetime | None = None,
) -> list[str]:
    now = now or datetime.now(UTC)
    problems: list[str] = []

    if outreach.state is not OutreachState.approved:
        problems.append(f"Draft must be approved first (it is {outreach.state.value}).")
    flags = unresolved_flags(outreach)
    if flags:
        problems.append(f"{len(flags)} unresolved critic flag(s).")

    contact = db.get(Contact, outreach.contact_id) if outreach.contact_id else None
    if contact is None:
        problems.append("No recipient.")
        return problems

    if is_suppressed(db, contact.email):
        problems.append(f"{contact.email} is on the suppression list.")

    day_start = now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    sent_today = (
        db.query(Outreach)
        .filter(Outreach.sent_at.is_not(None), Outreach.sent_at >= day_start)
        .count()
    )
    if sent_today >= daily_cap:
        problems.append(f"Daily cap reached ({sent_today}/{daily_cap}).")

    since = now - timedelta(days=dedupe_days)
    earlier = (
        db.query(Outreach, Contact)
        .outerjoin(Contact, Outreach.contact_id == Contact.id)
        .filter(
            Outreach.id != outreach.id,
            Outreach.state.in_(SENT_STATES),
            Outreach.sent_at >= since,
        )
        .all()
    )
    for other, other_contact in earlier:
        if other_contact is not None and other_contact.email == contact.email:
            problems.append(f"Already emailed {contact.email} in the last {dedupe_days} days.")
            break
        if outreach.company_id is not None and other.company_id == outreach.company_id:
            problems.append(f"Already contacted this company in the last {dedupe_days} days.")
            break
    return problems
