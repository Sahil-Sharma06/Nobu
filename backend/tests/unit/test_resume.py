import io
from pathlib import Path

import docx
import pytest
from sqlalchemy.orm import Session

from nobu.db.models import Fact, Profile
from nobu.llm.stub import StubLLM
from nobu.resume.extract import UnsupportedResume, extract_text
from nobu.resume.fact_bank import ResumeExists, ingest_resume
from tests.fixtures import RESUME_RESPONSE


def test_extract_txt_and_docx() -> None:
    assert extract_text("cv.txt", b"  Sahil\nPython  ") == "Sahil\nPython"
    buf = io.BytesIO()
    d = docx.Document()
    d.add_paragraph("Built Scouter")
    d.save(buf)
    assert extract_text("cv.DOCX", buf.getvalue()) == "Built Scouter"


def test_extract_rejects_unknown_and_empty() -> None:
    with pytest.raises(UnsupportedResume):
        extract_text("cv.png", b"x")
    with pytest.raises(UnsupportedResume):
        extract_text("cv.txt", b"   ")


def test_ingest_builds_fact_bank_once(db: Session, tmp_path: Path) -> None:
    llm = StubLLM({"extract_resume": RESUME_RESPONSE})
    ingest_resume(db, llm, tmp_path, "cv.txt", b"raw", "resume text")
    assert (tmp_path / "resume.txt").read_bytes() == b"raw"
    assert db.query(Fact).count() == len(RESUME_RESPONSE["facts"])
    profile = db.query(Profile).one()
    assert profile.name == "Sahil Sharma"
    assert profile.links["github"] == "https://github.com/sahil"
    with pytest.raises(ResumeExists):
        ingest_resume(db, llm, tmp_path, "cv.txt", b"raw", "resume text")
