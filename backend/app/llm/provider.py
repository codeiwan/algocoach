from typing import Protocol

from app.schemas.agent import AnalysisRequest, AnalysisResult


class LLMProvider(Protocol):
    """Common interface for LLM providers."""

    async def generate(self, prompt: str) -> str:
        """Generate a text response for the given prompt."""
        ...

    async def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        """Analyze a problem-solving snapshot."""
        ...

    async def aclose(self) -> None:
        """Release resources owned by the provider."""
        ...
