from app.schemas.agent import (
    AnalysisRequest,
    AnalysisResult,
    ProgressStatus,
)
from app.schemas.hint import (
    HintLevel,
    HintRequest,
    HintResult,
)
from app.schemas.problem import (
    ProblemStructureRequest,
    StructuredProblem,
)
from app.schemas.submission_review import (
    ReviewStatus,
    SubmissionReviewRequest,
    SubmissionReviewResult,
)


MOCK_HINT_MESSAGES: dict[HintLevel, str] = {
    HintLevel.DIRECTION: (
        "Mock 방향 힌트입니다. 문제의 입력 조건과 목표 출력을 "
        "비교해 보세요."
    ),
    HintLevel.ALGORITHM: (
        "Mock 알고리즘 힌트입니다. 입력 크기와 필요한 연산을 "
        "기준으로 접근 방법을 검토하세요."
    ),
    HintLevel.IMPLEMENTATION: (
        "Mock 구현 힌트입니다. 현재 코드에서 다음에 처리해야 할 "
        "단계를 확인해 보세요."
    ),
}


class MockLLMProvider:
    """Return predictable responses without actual LLM calls."""

    async def generate(self, prompt: str) -> str:
        return "Mock Provider 응답입니다. 실제 LLM은 호출하지 않았습니다."

    async def analyze(
        self,
        request: AnalysisRequest,
    ) -> AnalysisResult:
        if request.current_code.strip():
            progress_status = ProgressStatus.IMPLEMENTING
        else:
            progress_status = ProgressStatus.UNDERSTANDING

        return AnalysisResult(
            analyzed_revision=request.code_revision,
            algorithm=None,
            progress_status=progress_status,
            summary=(
                "Mock 분석 결과입니다. "
                "실제 코드 추론은 수행하지 않았습니다."
            ),
            positive_observation=None,
            complexity_estimate=None,
            issues=[],
        )

    async def structure_problem(
        self,
        request: ProblemStructureRequest,
    ) -> StructuredProblem:
        return StructuredProblem(
            title=None,
            goal=request.problem_text.strip(),
            input_format=None,
            output_format=None,
            constraints=[],
            examples=[],
            ambiguities=[],
        )

    async def generate_hint(
        self,
        request: HintRequest,
    ) -> HintResult:
        return HintResult(
            hinted_revision=request.code_revision,
            level=request.level,
            message=MOCK_HINT_MESSAGES[request.level],
            code_reference=None,
        )

    async def review_submission(
        self,
        request: SubmissionReviewRequest,
    ) -> SubmissionReviewResult:
        """
        Return UNCERTAIN rather than pretending code was reviewed.
        """

        return SubmissionReviewResult(
            reviewed_revision=request.code_revision,
            status=ReviewStatus.UNCERTAIN,
            summary=(
                "Mock 제출 전 점검 결과입니다. "
                "실제 코드 분석이나 테스트 실행은 수행하지 않았습니다."
            ),
            findings=[],
            complexity_assessment=None,
            suggested_checks=[],
        )

    async def aclose(self) -> None:
        pass
