from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    Response,
    status,
)

from app.schemas.session_completion import (
    SessionCompletionReceipt,
    SessionCompletionRequest,
)
from app.services.session_completions import (
    SessionAlreadyCompleted,
    SessionCompletionStore,
)


router = APIRouter(
    prefix="/api/v1/dev/sessions",
    tags=["Development"],
)


@router.post(
    "/complete",
    response_model=SessionCompletionReceipt,
    status_code=status.HTTP_201_CREATED,
)
async def complete_session(
    completion_request: SessionCompletionRequest,
    request: Request,
    response: Response,
) -> SessionCompletionReceipt:
    """
    Record the end of a coding session.

    External judge verdicts are user-reported.
    This endpoint never executes or judges source code.
    """

    store: SessionCompletionStore = (
        request.app.state.session_completion_store
    )

    try:
        outcome = await store.complete(completion_request)

    except SessionAlreadyCompleted as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "이미 다른 내용으로 종료된 풀이 세션입니다. "
                "기존 종료 기록을 변경할 수 없습니다."
            ),
        ) from error

    if outcome.created:
        response.status_code = status.HTTP_201_CREATED
    else:
        response.status_code = status.HTTP_200_OK

    return outcome.receipt
