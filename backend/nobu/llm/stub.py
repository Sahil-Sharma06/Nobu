"""Deterministic offline LLM for tests and local runs without a model.

Responses are registered per prompt name, either as a fixed dict or as a function of the
user message. Every call is recorded in `calls` so tests can assert on prompts.
"""

from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel

from nobu.llm.base import LLMError

T = TypeVar("T", bound=BaseModel)
Responder = dict[str, Any] | Callable[[str], dict[str, Any]]


class StubLLM:
    def __init__(self, responses: dict[str, Responder] | None = None) -> None:
        self.responses: dict[str, Responder] = dict(responses or {})
        self.calls: list[tuple[str, str, str]] = []

    def set(self, prompt_name: str, response: Responder) -> None:
        self.responses[prompt_name] = response

    def complete(self, prompt_name: str, system: str, user: str, schema: type[T]) -> T:
        self.calls.append((prompt_name, system, user))
        if prompt_name not in self.responses:
            raise LLMError(
                f"stub LLM has no answer for {prompt_name!r}. "
                "Set NOBU_LLM_PROVIDER (e.g. openai_compat) in .env to use a real model."
            )
        r = self.responses[prompt_name]
        data = r(user) if callable(r) else r
        return schema.model_validate(data)
