from sqlalchemy.orm import Session

from nobu.db.models import Fact, FactType, Outreach, OutreachState, Resume


def test_fact_bank_roundtrip(db: Session) -> None:
    r = Resume(file_path="data/resume.pdf", extracted_text="hi")
    r.facts.append(Fact(type=FactType.project, description="Scouter", tech=["python"]))
    db.add(r)
    db.commit()
    fact = db.query(Fact).one()
    assert fact.tech == ["python"]
    assert fact.resume_id == r.id


def test_outreach_defaults_to_drafted(db: Session) -> None:
    o = Outreach(role="backend intern")
    db.add(o)
    db.commit()
    assert o.state is OutreachState.drafted
    assert o.critic_flags == []
