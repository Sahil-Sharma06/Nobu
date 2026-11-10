from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session, sessionmaker

from nobu.config import Settings
from nobu.db.models import Base
from nobu.db.session import make_engine
from nobu.llm.stub import StubLLM
from nobu.pipeline.core import Deps
from nobu.providers.contacts import NullContactProvider
from nobu.providers.fetch import FakeFetcher
from nobu.providers.search import FakeSearch
from nobu.resume.fact_bank import ingest_resume
from tests.fixtures import ACME_PAGES, stub_responses


@pytest.fixture
def db() -> Iterator[Session]:
    engine = make_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def _fk_on(conn: Any, _rec: Any) -> None:
        conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as session:
        yield session


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, data_dir=tmp_path / "data")


@pytest.fixture
def deps(db: Session, settings: Settings) -> Deps:
    return Deps(
        db=db,
        llm=StubLLM(stub_responses()),
        fetcher=FakeFetcher(ACME_PAGES),
        search=FakeSearch(),
        contacts=NullContactProvider(),
        settings=settings,
    )


@pytest.fixture
def with_resume(deps: Deps) -> Deps:
    ingest_resume(deps.db, deps.llm, deps.settings.data_dir, "cv.txt", b"cv", "cv text")
    return deps
