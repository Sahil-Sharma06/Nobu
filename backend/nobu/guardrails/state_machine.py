"""Outreach state machine (spec section 9). Every transition writes an event row."""

from typing import Any

from sqlalchemy.orm import Session

from nobu.db.models import Actor, Event, Outreach
from nobu.db.models import OutreachState as S

TRANSITIONS: dict[S, set[S]] = {
    S.drafted: {S.approved, S.discarded},
    S.approved: {S.sent, S.drafted, S.discarded},  # editing an approved draft un-approves it
    S.sent: {S.replied, S.bounced, S.followup_1_due, S.closed},
    S.followup_1_due: {S.followup_1_sent, S.replied, S.bounced, S.closed},
    S.followup_1_sent: {S.followup_2_due, S.replied, S.bounced, S.closed},
    S.followup_2_due: {S.followup_2_sent, S.replied, S.bounced, S.closed},
    S.followup_2_sent: {S.replied, S.bounced, S.closed},
    S.replied: {S.closed},
    S.bounced: {S.closed},
    S.closed: set(),
    S.discarded: set(),
}


class InvalidTransition(ValueError):
    pass


def transition(
    db: Session,
    outreach: Outreach,
    to: S,
    actor: Actor,
    detail: dict[str, Any] | None = None,
) -> None:
    frm = outreach.state
    if to not in TRANSITIONS[frm]:
        raise InvalidTransition(f"cannot go from {frm.value} to {to.value}")
    outreach.state = to
    db.add(
        Event(
            outreach_id=outreach.id,
            type=f"state:{frm.value}->{to.value}",
            detail=detail or {},
            actor=actor,
        )
    )
