from app.schemas.agent import (
    AnalysisRequest,
    AnalysisResult,
    ProgressStatus,
)
from app.schemas.problem import (
    ProblemStructureRequest,
    StructuredProblem,
)


class MockLLMProvider:
    """Return predictable responses without calling an actual LLM."""

    async def generate(self, prompt: str) -> str:
        """Return a fixed text response."""
        return "Mock Provider 응답입니다. 실제 LLM은 호출하지 않았습니다."

    async def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        """Return a structured mock code analysis."""

        if request.current_code.strip():
            progress_status = ProgressStatus.IMPLEMENTING
        else:
            progress_status = ProgressStatus.UNDERSTANDING

        return AnalysisResult(
            analyzed_revision=request.code_revision,
            algorithm=None,
            progress_status=progress_status,
            summary="Mock 분석 결과입니다. 실제 코드 추론은 수행하지 않았습니다.",
            positive_observation=None,
            complexity_estimate=None,
            issues=[],
        )

    async def structure_problem(
        self,
        request: ProblemStructureRequest,
    ) -> StructuredProblem:
        """Preserve the original problem without AI extraction."""

        return StructuredProblem(
            title=None,
            goal=request.problem_text.strip(),
            input_format=None,
            output_format=None,
            constraints=[],
            examples=[],
            ambiguities=[],
        )

    async def aclose(self) -> None:
        """No resources need to be released by the mock provider."""
        pass
