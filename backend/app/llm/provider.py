from typing import Protocol

from app.schemas.agent import AnalysisRequest, AnalysisResult
from app.schemas.problem import ProblemStructureRequest, StructuredProblem


class LLMProvider(Protocol):
    """Common interface for LLM providers."""

    async def generate(self, prompt: str) -> str:
        """Generate a text response for the given prompt."""
        ...

    async def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        """Analyze a problem-solving snapshot."""
        ...

    async def structure_problem(
        self,
        request: ProblemStructureRequest,
    ) -> StructuredProblem:
        """Extract structured information from a coding problem."""
        ...

    async def aclose(self) -> None:
        """Release resources owned by the provider."""
        ...
