from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from nobu.config import Settings
from nobu.db.models import Actor, Company, Contact, Event, Outreach, OutreachState, Suppression
from nobu.guardrails import send_policy
from nobu.guardrails.sending import DryRunTransport, SendBlocked, make_transport, send
from nobu.guardrails.state_machine import InvalidTransition, transition

NOW = datetime(2026, 11, 11, 12, tzinfo=UTC)


def make_outreach(
    db: Session,
    email: str = "priya@acme.dev",
    domain: str = "acme.dev",
    state: OutreachState = OutreachState.approved,
    flags: list[dict[str, object]] | None = None,
    sent_at: datetime | None = None,
) -> Outreach:
    company = db.query(Company).filter_by(domain=domain).first() or Company(
        name=domain, domain=domain
    )
    db.add(company)
    db.flush()
    contact = Contact(company_id=company.id, email=email, confidence=0.9)
    db.add(contact)
    db.flush()
    o = Outreach(
        company_id=company.id,
        contact_id=contact.id,
        subject="s",
        body="b",
        state=state,
        critic_flags=flags or [],
        sent_at=sent_at,
    )
    db.add(o)
    db.commit()
    return o


def problems(db: Session, o: Outreach, cap: int = 15, days: int = 60) -> list[str]:
    return send_policy.check(db, o, daily_cap=cap, dedupe_days=days, now=NOW)


def test_clean_approved_outreach_passes(db: Session) -> None:
    assert problems(db, make_outreach(db)) == []


def test_unresolved_critic_flag_blocks_until_resolved(db: Session) -> None:
    o = make_outreach(db, flags=[{"code": "too_long", "message": "x", "resolved": False}])
    assert any("critic flag" in p for p in problems(db, o))
    o.critic_flags = [{"code": "too_long", "message": "x", "resolved": True}]
    assert problems(db, o) == []


def test_must_be_approved(db: Session) -> None:
    o = make_outreach(db, state=OutreachState.drafted)
    assert any("approved" in p for p in problems(db, o))


def test_suppression_by_email_and_domain(db: Session) -> None:
    o = make_outreach(db)
    db.add(Suppression(value="priya@acme.dev"))
    db.commit()
    assert any("suppression" in p for p in problems(db, o))
    o2 = make_outreach(db, email="x@other.dev", domain="other.dev")
    db.add(Suppression(value="other.dev"))
    db.commit()
    assert any("suppression" in p for p in problems(db, o2))


def test_daily_cap(db: Session) -> None:
    for i in range(2):
        make_outreach(
            db, email=f"a{i}@c{i}.dev", domain=f"c{i}.dev", state=OutreachState.sent, sent_at=NOW
        )
    o = make_outreach(db, email="new@new.dev", domain="new.dev")
    assert any("Daily cap" in p for p in problems(db, o, cap=2))
    assert problems(db, o, cap=3) == []


def test_daily_cap_ignores_yesterday(db: Session) -> None:
    make_outreach(
        db,
        email="a@b.dev",
        domain="b.dev",
        state=OutreachState.sent,
        sent_at=NOW - timedelta(days=1),
    )
    assert problems(db, make_outreach(db), cap=1) == []


def test_dedupe_same_contact_and_same_company(db: Session) -> None:
    make_outreach(db, state=OutreachState.sent, sent_at=NOW - timedelta(days=10))
    same_person = make_outreach(db)
    assert any("Already emailed" in p for p in problems(db, same_person))
    other_person = make_outreach(db, email="ravi@acme.dev")
    assert any("this company" in p for p in problems(db, other_person))


def test_dedupe_window_expires(db: Session) -> None:
    make_outreach(db, state=OutreachState.sent, sent_at=NOW - timedelta(days=61))
    assert problems(db, make_outreach(db), days=60) == []


def test_state_machine_rejects_illegal_and_logs_events(db: Session) -> None:
    o = make_outreach(db, state=OutreachState.drafted)
    with pytest.raises(InvalidTransition):
        transition(db, o, OutreachState.sent, Actor.user)
    transition(db, o, OutreachState.approved, Actor.user)
    db.commit()
    assert db.query(Event).one().type == "state:drafted->approved"


def test_dry_run_send_writes_eml_and_marks_sent(db: Session, tmp_path: Path) -> None:
    o = make_outreach(db)
    settings = Settings(_env_file=None, data_dir=tmp_path)
    msg_id = send(db, o, settings, DryRunTransport(tmp_path / "outbox"), now=NOW)
    assert msg_id.startswith("dry-run:")
    eml = (tmp_path / "outbox" / f"outreach-{o.id}.eml").read_text()
    assert "To: priya@acme.dev" in eml
    assert o.state is OutreachState.sent and o.sent_at == NOW
    event = db.query(Event).one()
    assert event.detail["dry_run"] is True


def test_send_blocked_with_flags_leaves_state(db: Session, tmp_path: Path) -> None:
    o = make_outreach(db, flags=[{"code": "x", "message": "x", "resolved": False}])
    settings = Settings(_env_file=None, data_dir=tmp_path)
    with pytest.raises(SendBlocked):
        send(db, o, settings, DryRunTransport(tmp_path), now=NOW)
    assert o.state is OutreachState.approved
    assert not (tmp_path / f"outreach-{o.id}.eml").exists()


def test_real_sending_refused_in_phase_1(tmp_path: Path) -> None:
    with pytest.raises(SendBlocked):
        make_transport(Settings(_env_file=None, dry_run=False, data_dir=tmp_path))
    assert make_transport(Settings(_env_file=None, data_dir=tmp_path)).dry_run
