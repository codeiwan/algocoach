import logging

from fastapi import APIRouter, HTTPException, Request

from app.llm.provider import LLMProvider
from app.schemas.submission_review import (
    SubmissionReviewRequest,
    SubmissionReviewResult,
)


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/dev/submission",
    tags=["Development"],
)


@router.post(
    "/review",
    response_model=SubmissionReviewResult,
)
async def review_submission(
    review_request: SubmissionReviewRequest,
    request: Request,
) -> SubmissionReviewResult:
    """
    Perform an AI-only pre-submission review.

    This endpoint does not execute, compile, or judge code.
    The configured provider performs a static assessment.
    """

    provider: LLMProvider = request.app.state.llm_provider

    try:
        result = await provider.review_submission(
            review_request
        )
    except Exception as error:
        logger.exception(
            "Pre-submission review provider failed."
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "제출 전 AI 점검을 완료하지 못했습니다. "
                "잠시 후 다시 시도해 주세요."
            ),
        ) from error

    # Never return a review for the wrong code revision.
    if result.reviewed_revision != review_request.code_revision:
        logger.error(
            "Submission review revision mismatch: "
            "requested=%s, returned=%s",
            review_request.code_revision,
            result.reviewed_revision,
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "요청한 코드와 점검 결과의 Revision이 "
                "일치하지 않습니다."
            ),
        )

    return result
