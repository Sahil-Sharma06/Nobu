"""ORM models. Mirrors docs/PROJECT.md section 10, plus audit_step for pipeline auditing."""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, list[Any]: JSON}


class OutreachState(enum.StrEnum):
    drafted = "drafted"
    approved = "approved"
    sent = "sent"
    replied = "replied"
    bounced = "bounced"
    followup_1_due = "followup_1_due"
    followup_1_sent = "followup_1_sent"
    followup_2_due = "followup_2_due"
    followup_2_sent = "followup_2_sent"
    closed = "closed"
    discarded = "discarded"


class Actor(enum.StrEnum):
    user = "user"
    agent = "agent"
    system = "system"


class FactType(enum.StrEnum):
    project = "project"
    experience = "experience"
    skill = "skill"
    achievement = "achievement"
    education = "education"


class Profile(Base):
    __tablename__ = "profile"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    tone: Mapped[str] = mapped_column(String(100), default="friendly, direct")
    sign_off: Mapped[str] = mapped_column(String(200), default="")
    links: Mapped[dict[str, Any]] = mapped_column(default=dict)
    target_roles: Mapped[list[Any]] = mapped_column(default=list)
    daily_cap: Mapped[int] = mapped_column(default=15)
    dry_run: Mapped[bool] = mapped_column(default=True)


class Resume(Base):
    __tablename__ = "resume"
    id: Mapped[int] = mapped_column(primary_key=True)
    file_path: Mapped[str] = mapped_column(String(500))
    extracted_text: Mapped[str] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    facts: Mapped[list[Fact]] = relationship(back_populates="resume", cascade="all, delete")


class Fact(Base):
    __tablename__ = "fact"
    id: Mapped[int] = mapped_column(primary_key=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resume.id", ondelete="CASCADE"))
    type: Mapped[FactType] = mapped_column(Enum(FactType, native_enum=False))
    description: Mapped[str] = mapped_column(Text)
    tech: Mapped[list[Any]] = mapped_column(default=list)
    outcome: Mapped[str] = mapped_column(Text, default="")
    links: Mapped[list[Any]] = mapped_column(default=list)
    tags: Mapped[list[Any]] = mapped_column(default=list)
    resume: Mapped[Resume] = relationship(back_populates="facts")


class Company(Base):
    __tablename__ = "company"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    domain: Mapped[str] = mapped_column(String(200), default="", index=True)
    brief: Mapped[dict[str, Any]] = mapped_column(default=dict)
    sources: Mapped[list[Any]] = mapped_column(default=list)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Contact(Base):
    __tablename__ = "contact"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200), default="")
    title: Mapped[str] = mapped_column(String(200), default="")
    email: Mapped[str] = mapped_column(String(320), index=True)
    source: Mapped[str] = mapped_column(String(500), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Outreach(Base):
    __tablename__ = "outreach"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("company.id", ondelete="CASCADE"))
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contact.id", ondelete="SET NULL"))
    role: Mapped[str] = mapped_column(String(200), default="")
    state: Mapped[OutreachState] = mapped_column(
        Enum(OutreachState, native_enum=False), default=OutreachState.drafted
    )
    subject: Mapped[str] = mapped_column(String(300), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    highlighted_fact_ids: Mapped[list[Any]] = mapped_column(default=list)
    rationale: Mapped[dict[str, Any]] = mapped_column(default=dict)
    critic_flags: Mapped[list[Any]] = mapped_column(default=list)
    thread_id: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Event(Base):
    __tablename__ = "event"
    id: Mapped[int] = mapped_column(primary_key=True)
    outreach_id: Mapped[int] = mapped_column(ForeignKey("outreach.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(100))
    detail: Mapped[dict[str, Any]] = mapped_column(default=dict)
    actor: Mapped[Actor] = mapped_column(Enum(Actor, native_enum=False))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Suppression(Base):
    __tablename__ = "suppression"
    id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[str] = mapped_column(String(320), unique=True)  # email or domain, lowercase
    reason: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditStep(Base):
    """One row per pipeline node execution: inputs, outputs and sources, for auditability."""

    __tablename__ = "audit_step"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    outreach_id: Mapped[int | None] = mapped_column(ForeignKey("outreach.id", ondelete="CASCADE"))
    node: Mapped[str] = mapped_column(String(50))
    inputs: Mapped[dict[str, Any]] = mapped_column(default=dict)
    outputs: Mapped[dict[str, Any]] = mapped_column(default=dict)
    sources: Mapped[list[Any]] = mapped_column(default=list)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
