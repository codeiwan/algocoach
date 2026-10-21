from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    Response,
    status,
)

from app.schemas.session_feedback import (
    SessionFeedbackReceipt,
    SessionFeedbackRequest,
)
from app.services.session_feedback import (
    SessionFeedbackAlreadyRecorded,
    SessionFeedbackStore,
    SessionNotCompleted,
)


router = APIRouter(
    prefix="/api/v1/dev/sessions",
    tags=["Development"],
)


@router.post(
    "/feedback",
    response_model=SessionFeedbackReceipt,
    status_code=status.HTTP_201_CREATED,
)
async def record_session_feedback(
    feedback_request: SessionFeedbackRequest,
    request: Request,
    response: Response,
) -> SessionFeedbackReceipt:
    """
    Record learner feedback after session completion.

    Feedback is learner-reported and does not represent
    a judge verdict or an automated assessment.
    """

    store: SessionFeedbackStore = (
        request.app.state.session_feedback_store
    )

    try:
        outcome = await store.record(feedback_request)

    except SessionNotCompleted as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "완료된 풀이 세션을 찾을 수 없습니다. "
                "풀이 종료를 먼저 완료해 주세요."
            ),
        ) from error

    except SessionFeedbackAlreadyRecorded as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "이 풀이 세션에는 이미 다른 내용의 "
                "설문이 기록되어 있습니다."
            ),
        ) from error

    response.status_code = (
        status.HTTP_201_CREATED
        if outcome.created
        else status.HTTP_200_OK
    )

    return outcome.receipt
