from typing import Literal

from app.llm.mock import MockLLMProvider
from app.llm.openai_provider import OpenAILLMProvider
from app.llm.provider import LLMProvider


def create_llm_provider(
    provider_name: Literal["mock", "openai"],
    *,
    api_key: str | None = None,
    model: str = "gpt-5.4-mini",
) -> LLMProvider:
    """Create the configured LLM provider."""

    if provider_name == "mock":
        return MockLLMProvider()

    if provider_name == "openai":
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY is required for the OpenAI provider."
            )

        return OpenAILLMProvider(
            api_key=api_key,
            model=model,
        )

    raise ValueError(
        f"Unsupported LLM provider: {provider_name}"
    )
