"""The single entry point for every LLM call in Nobu.

All callers use `LLMClient.complete(...)`, which returns a validated Pydantic object.
`prompt_name` identifies the call site (e.g. "parse_command") so the stub can answer
deterministically and so calls can be logged per node.
"""

from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


class LLMClient(Protocol):
    def complete(self, prompt_name: str, system: str, user: str, schema: type[T]) -> T: ...
