from fastapi import APIRouter, HTTPException, Request

from app.llm.provider import LLMProvider
from app.schemas.hint import NextHintRequest, HintResult
from app.services.hint_sessions import (
    HintLimitReached,
    HintSessionStore,
)


router = APIRouter(
    prefix="/api/v1/dev/hints",
    tags=["Development"],
)


@router.post("/next", response_model=HintResult)
async def generate_next_hint(
    hint_request: NextHintRequest,
    request: Request,
) -> HintResult:
    """Generate the next progressive hint for a session."""

    provider: LLMProvider = request.app.state.llm_provider
    store: HintSessionStore = request.app.state.hint_session_store

    try:
        return await store.generate_next(
            request=hint_request,
            provider=provider,
        )
    except HintLimitReached as error:
        raise HTTPException(
            status_code=409,
            detail=(
                "이미 3단계 힌트를 모두 제공했습니다. "
                "추가 힌트는 제공하지 않습니다."
            ),
        ) from error
