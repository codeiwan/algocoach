import asyncio

from app.agents.hint_policy import evaluate_hint_policy
from app.llm.provider import LLMProvider
from app.schemas.hint import (
    HintRequest,
    HintResult,
    HintSource,
    NextHintRequest,
)


class HintLimitReached(Exception):
    """Raised when all progressive hints were delivered."""


class HintSessionStore:
    """
    Manage progressive hints for each session.

    This implementation stores data in application memory.
    It is intended for the development MVP.
    """

    def __init__(self) -> None:
        self._history: dict[str, list[HintResult]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def generate_next(
        self,
        request: NextHintRequest,
        provider: LLMProvider,
    ) -> HintResult:
        """
        Generate the next hint and commit it only after success.

        A per-session lock prevents concurrent requests from
        generating the same progression step.
        """

        session_id = request.session_id

        lock = self._locks.setdefault(
            session_id,
            asyncio.Lock(),
        )

        async with lock:
            history = self._history.get(session_id, [])

            previous_level = (
                history[-1].level
                if history
                else None
            )

            decision = evaluate_hint_policy(
                previous_level=previous_level,
                source=HintSource.USER_REQUEST,
            )

            if not decision.allowed or decision.next_level is None:
                raise HintLimitReached(
                    "All progressive hint levels have been delivered."
                )

            # The server determines the next level and prior hints.
            hint_request = HintRequest(
                session_id=session_id,
                code_revision=request.code_revision,
                problem_text=request.problem_text,
                current_code=request.current_code,
                language=request.language,
                level=decision.next_level,
                previous_hints=[
                    hint.message
                    for hint in history
                ],
            )

            # A failed provider call must not advance progression.
            result = await provider.generate_hint(hint_request)

            # Validate the provider's response before committing.
            if result.level != hint_request.level:
                raise ValueError(
                    "Generated hint level does not match the request."
                )

            if result.hinted_revision != hint_request.code_revision:
                raise ValueError(
                    "Generated hint revision does not match the request."
                )

            if not result.message.strip():
                raise ValueError(
                    "Generated hint message must not be blank."
                )

            # Commit only after successful generation and validation.
            self._history.setdefault(
                session_id,
                [],
            ).append(result)

            return result
