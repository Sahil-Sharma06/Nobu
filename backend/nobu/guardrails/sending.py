"""Send an approved outreach. Phase 1 only has the dry-run transport: the message is built
and written to data/outbox as a .eml file; nothing leaves the machine."""

from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Protocol

from sqlalchemy.orm import Session

from nobu.config import Settings
from nobu.db.models import Actor, Contact, Outreach, OutreachState, Profile
from nobu.guardrails import send_policy
from nobu.guardrails.state_machine import transition


class SendBlocked(RuntimeError):
    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


class Transport(Protocol):
    dry_run: bool

    def send(self, msg: EmailMessage, outreach_id: int) -> str: ...


class DryRunTransport:
    dry_run = True

    def __init__(self, outbox: Path) -> None:
        self.outbox = outbox

    def send(self, msg: EmailMessage, outreach_id: int) -> str:
        self.outbox.mkdir(parents=True, exist_ok=True)
        path = self.outbox / f"outreach-{outreach_id}.eml"
        path.write_bytes(bytes(msg))
        return f"dry-run:{path.name}"


def make_transport(settings: Settings) -> Transport:
    if not settings.dry_run:
        raise SendBlocked(["Real sending is not available until Phase 2 (Gmail). Keep dry-run on."])
    return DryRunTransport(settings.data_dir / "outbox")


def build_message(outreach: Outreach, contact: Contact, profile: Profile | None) -> EmailMessage:
    msg = EmailMessage()
    msg["To"] = contact.email
    msg["From"] = (profile.name if profile else "") or "me"
    msg["Subject"] = outreach.subject
    msg.set_content(outreach.body)
    return msg


def send(
    db: Session,
    outreach: Outreach,
    settings: Settings,
    transport: Transport,
    now: datetime | None = None,
) -> str:
    now = now or datetime.now(UTC)
    profile = db.query(Profile).first()
    cap = profile.daily_cap if profile else settings.daily_cap
    problems = send_policy.check(
        db, outreach, daily_cap=cap, dedupe_days=settings.dedupe_days, now=now
    )
    if problems:
        raise SendBlocked(problems)
    contact = db.get(Contact, outreach.contact_id)
    assert contact is not None  # check() guarantees a recipient
    message_id = transport.send(build_message(outreach, contact, profile), outreach.id)
    outreach.thread_id = message_id
    outreach.sent_at = now
    transition(
        db,
        outreach,
        OutreachState.sent,
        Actor.user,
        {"to": contact.email, "dry_run": transport.dry_run, "message_id": message_id},
    )
    db.commit()
    return message_id
