from collections.abc import Iterator

from fastapi import Depends
from sqlalchemy.orm import Session

from nobu.config import get_settings
from nobu.db.session import get_db
from nobu.llm.factory import make_llm
from nobu.pipeline.core import Deps
from nobu.providers.contacts import NullContactProvider
from nobu.providers.fetch import HttpFetcher
from nobu.providers.search import DdgsSearch


def get_deps(db: Session = Depends(get_db)) -> Iterator[Deps]:  # noqa: B008
    settings = get_settings()
    yield Deps(
        db=db,
        llm=make_llm(settings),
        fetcher=HttpFetcher(),
        search=DdgsSearch(),
        contacts=NullContactProvider(),
        settings=settings,
    )
