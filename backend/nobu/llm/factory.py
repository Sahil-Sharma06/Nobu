from nobu.config import Settings
from nobu.llm.base import LLMClient
from nobu.llm.providers import AnthropicLLM, OllamaLLM
from nobu.llm.stub import StubLLM


def make_llm(settings: Settings) -> LLMClient:
    if settings.llm_provider == "ollama":
        return OllamaLLM(settings.ollama_url, settings.llm_model)
    if settings.llm_provider == "anthropic":
        return AnthropicLLM(settings.anthropic_api_key, settings.llm_model)
    return StubLLM()
