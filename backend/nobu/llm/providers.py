"""Real LLM providers. Both return schema-validated objects."""

import json
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from nobu.llm.base import LLMError

T = TypeVar("T", bound=BaseModel)


class OllamaLLM:
    """Free local models via Ollama's /api/chat with a JSON-schema `format`."""

    def __init__(self, base_url: str, model: str, timeout: float = 180.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def complete(self, prompt_name: str, system: str, user: str, schema: type[T]) -> T:
        payload = {
            "model": self.model,
            "stream": False,
            "format": schema.model_json_schema(),
            "options": {"temperature": 0.2},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            resp = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
            resp.raise_for_status()
            content = resp.json()["message"]["content"]
            return schema.model_validate_json(content)
        except (httpx.HTTPError, KeyError, ValidationError) as e:
            raise LLMError(f"ollama call {prompt_name!r} failed: {e}") from e


class AnthropicLLM:
    """Anthropic Messages API; structured output via a forced tool call."""

    def __init__(self, api_key: str, model: str, max_tokens: int = 2048) -> None:
        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY is not set")
        import anthropic

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    def complete(self, prompt_name: str, system: str, user: str, schema: type[T]) -> T:
        tool: Any = {
            "name": "respond",
            "description": "Return the answer in this structure.",
            "input_schema": schema.model_json_schema(),
        }
        try:
            msg = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                tools=[tool],
                tool_choice={"type": "tool", "name": "respond"},
            )
            for block in msg.content:
                if block.type == "tool_use":
                    return schema.model_validate(block.input)
            raise LLMError(f"no tool_use block in response: {json.dumps(str(msg.content))}")
        except ValidationError as e:
            raise LLMError(f"anthropic call {prompt_name!r} returned invalid data: {e}") from e
