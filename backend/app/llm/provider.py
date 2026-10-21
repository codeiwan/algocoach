from typing import Protocol

from app.schemas.agent import AnalysisRequest, AnalysisResult
from app.schemas.hint import HintRequest, HintResult
from app.schemas.problem import (
    ProblemStructureRequest,
    StructuredProblem,
)
from app.schemas.submission_review import (
    SubmissionReviewRequest,
    SubmissionReviewResult,
)


class LLMProvider(Protocol):
    """Common interface for AlgoCoach LLM providers."""

    async def generate(self, prompt: str) -> str:
        """Generate a plain-text response."""
        ...

    async def analyze(
        self,
        request: AnalysisRequest,
    ) -> AnalysisResult:
        """Analyze the current problem-solving snapshot."""
        ...

    async def structure_problem(
        self,
        request: ProblemStructureRequest,
    ) -> StructuredProblem:
        """Extract structured coding-problem information."""
        ...

    async def generate_hint(
        self,
        request: HintRequest,
    ) -> HintResult:
        """Generate progressive coding guidance."""
        ...

    async def review_submission(
        self,
        request: SubmissionReviewRequest,
    ) -> SubmissionReviewResult:
        """Perform a pre-submission static code review."""
        ...

    async def aclose(self) -> None:
        """Release provider resources."""
        ...
