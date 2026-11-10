from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session, sessionmaker

from nobu.db.models import Base
from nobu.db.session import make_engine


@pytest.fixture
def db() -> Iterator[Session]:
    engine = make_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def _fk_on(conn: Any, _rec: Any) -> None:
        conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as session:
        yield session
