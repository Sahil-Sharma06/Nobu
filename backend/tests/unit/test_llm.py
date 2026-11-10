from typing import Any

import httpx
import pytest
from pydantic import BaseModel

from nobu.config import Settings
from nobu.llm.base import LLMError
from nobu.llm.factory import make_llm
from nobu.llm.providers import AnthropicLLM, OllamaLLM
from nobu.llm.stub import StubLLM


class Answer(BaseModel):
    value: int


def test_stub_fixed_and_callable() -> None:
    llm = StubLLM({"a": {"value": 1}, "b": lambda user: {"value": len(user)}})
    assert llm.complete("a", "sys", "x", Answer).value == 1
    assert llm.complete("b", "sys", "abcd", Answer).value == 4
    assert [c[0] for c in llm.calls] == ["a", "b"]


def test_stub_unknown_prompt_raises() -> None:
    with pytest.raises(LLMError):
        StubLLM().complete("nope", "", "", Answer)


def test_factory_selects_provider() -> None:
    assert isinstance(make_llm(Settings(_env_file=None)), StubLLM)
    s = Settings(_env_file=None, llm_provider="ollama", llm_model="m")
    llm = make_llm(s)
    assert isinstance(llm, OllamaLLM) and llm.model == "m"


def test_anthropic_requires_key() -> None:
    with pytest.raises(LLMError):
        AnthropicLLM(api_key="", model="m")


def test_ollama_parses_schema_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, json: dict[str, Any], timeout: float) -> httpx.Response:
        assert json["format"]["properties"]["value"]["type"] == "integer"
        return httpx.Response(
            200,
            json={"message": {"content": '{"value": 7}'}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    assert OllamaLLM("http://x", "m").complete("p", "s", "u", Answer).value == 7
