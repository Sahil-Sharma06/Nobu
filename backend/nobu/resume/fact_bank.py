"""Turn resume text into the fact bank, the only source of claims about the user."""

from pathlib import Path

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from nobu.db.models import Fact, FactType, Profile, Resume
from nobu.llm.base import LLMClient

SYSTEM = """You extract a structured fact bank from a fresher's resume.
Rules:
- Only include what the resume actually states. Never invent numbers, tech or outcomes.
- One fact per project, job/internship, notable achievement, education entry.
- Group skills into at most 3 'skill' facts (e.g. languages, frameworks, tools).
- description: one or two plain sentences. outcome: stated results/metrics only, else "".
- links: URLs that appear in the resume for that item.
- Also return the candidate's name and their personal links (GitHub, portfolio, LinkedIn)."""


class ExtractedFact(BaseModel):
    type: FactType
    description: str
    tech: list[str] = Field(default_factory=list)
    outcome: str = ""
    links: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class ExtractedResume(BaseModel):
    name: str = ""
    links: dict[str, str] = Field(default_factory=dict)
    facts: list[ExtractedFact]


class ResumeExists(RuntimeError):
    pass


def ingest_resume(
    db: Session, llm: LLMClient, data_dir: Path, filename: str, data: bytes, text: str
) -> Resume:
    """Save the file under data_dir, build facts, prefill an empty profile. One-time only."""
    if db.query(Resume).first() is not None:
        raise ResumeExists("a resume is already uploaded; delete your data to replace it")
    extracted = llm.complete("extract_resume", SYSTEM, text, ExtractedResume)

    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / f"resume{Path(filename).suffix.lower()}"
    path.write_bytes(data)

    resume = Resume(file_path=str(path), extracted_text=text)
    for f in extracted.facts:
        resume.facts.append(Fact(**f.model_dump()))
    db.add(resume)

    profile = get_profile(db)
    if not profile.name:
        profile.name = extracted.name
    if not profile.links:
        profile.links = extracted.links
    db.commit()
    return resume


def get_profile(db: Session) -> Profile:
    profile = db.query(Profile).first()
    if profile is None:
        profile = Profile()
        db.add(profile)
        db.flush()
    return profile
