"""Any OpenAI-compatible chat-completions API (NVIDIA build.nvidia.com, Mistral, OpenRouter, ...).

Structured output is obtained with a forced function call, which is more widely supported
across these providers than JSON response-format enforcement. If a provider ignores the
forced call and answers in plain text, the text is parsed as JSON as a fallback.
"""

import json
import re
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from nobu.llm.base import LLMError

T = TypeVar("T", bound=BaseModel)
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")


def inline_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Resolve local $defs/$ref so providers that reject $ref still accept the schema."""
    defs = schema.get("$defs", {})

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/$defs/"):
                return walk(defs[ref.removeprefix("#/$defs/")])
            return {k: walk(v) for k, v in node.items() if k != "$defs"}
        if isinstance(node, list):
            return [walk(x) for x in node]
        return node

    result: dict[str, Any] = walk(schema)
    return result


class OpenAICompatLLM:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 180.0) -> None:
        if not base_url or not api_key:
            raise LLMError("NOBU_LLM_BASE_URL and NOBU_LLM_API_KEY must be set")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def complete(self, prompt_name: str, system: str, user: str, schema: type[T]) -> T:
        payload = {
            "model": self.model,
            "temperature": 0.2,
            "max_tokens": 4096,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "respond",
                        "description": "Return the answer in this structure.",
                        "parameters": inline_schema(schema.model_json_schema()),
                    },
                }
            ],
            "tool_choice": {"type": "function", "function": {"name": "respond"}},
        }
        try:
            resp = httpx.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            message = resp.json()["choices"][0]["message"]
            calls = message.get("tool_calls") or []
            if calls:
                return schema.model_validate_json(calls[0]["function"]["arguments"])
            content = _FENCE.sub("", (message.get("content") or "").strip())
            return schema.model_validate(json.loads(content))
        except httpx.HTTPStatusError as e:
            raise LLMError(
                f"{prompt_name!r}: HTTP {e.response.status_code}: {e.response.text[:300]}"
            ) from e
        except (httpx.HTTPError, KeyError, IndexError, ValueError, ValidationError) as e:
            raise LLMError(f"{prompt_name!r}: bad response: {e}") from e
