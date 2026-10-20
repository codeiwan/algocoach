from typing import Protocol


class LLMProvider(Protocol):
    """Common interface for LLM providers."""

    async def generate(self, prompt: str) -> str:
        """Generate a response for the given prompt."""
        ...

    async def aclose(self) -> None:
        """Release resources owned by the provider."""
        ...