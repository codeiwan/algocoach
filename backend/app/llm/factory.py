from typing import Literal

from app.llm.mock import MockLLMProvider
from app.llm.provider import LLMProvider


def create_llm_provider(
    provider_name: Literal["mock", "openai"],
) -> LLMProvider:
    """Create the configured LLM provider."""

    if provider_name == "mock":
        return MockLLMProvider()

    if provider_name == "openai":
        raise NotImplementedError(
            "OpenAI Provider is not implemented yet. "
            "Use LLM_PROVIDER=mock for now."
        )

    raise ValueError(f"Unsupported LLM provider: {provider_name}")