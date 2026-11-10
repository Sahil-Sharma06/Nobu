"""Shared pipeline plumbing: dependencies bundle and per-node audit recording."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TypeVar
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy.orm import Session

from nobu.config import Settings
from nobu.db.models import AuditStep
from nobu.llm.base import LLMClient
from nobu.providers.contacts import ContactProvider
from nobu.providers.fetch import Fetcher
from nobu.providers.search import SearchProvider

OutT = TypeVar("OutT", bound=BaseModel)


class NodeError(RuntimeError):
    """A node could not produce a usable result; the message is shown to the user."""


@dataclass
class Deps:
    db: Session
    llm: LLMClient
    fetcher: Fetcher
    search: SearchProvider
    contacts: ContactProvider
    settings: Settings
    run_id: str = field(default_factory=lambda: uuid4().hex)


def audited(deps: Deps, node: str, inp: BaseModel, fn: Callable[[], OutT]) -> OutT:
    """Run a node and persist its inputs, outputs, source URLs or error."""
    step = AuditStep(run_id=deps.run_id, node=node, inputs=inp.model_dump(mode="json"))
    try:
        out = fn()
    except Exception as e:
        step.error = f"{type(e).__name__}: {e}"
        deps.db.add(step)
        deps.db.commit()
        raise
    step.outputs = out.model_dump(mode="json")
    step.sources = list(getattr(out, "sources", []))
    deps.db.add(step)
    deps.db.commit()
    return out
