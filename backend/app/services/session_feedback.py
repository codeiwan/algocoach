import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

from app.schemas.session_feedback import (
    SessionFeedbackReceipt,
    SessionFeedbackRequest,
)
from app.services.session_completions import (
    SessionCompletionStore,
)


class SessionNotCompleted(Exception):
    """Raised when feedback is sent for a session not completed."""


class SessionFeedbackAlreadyRecorded(Exception):
    """Raised when existing feedback is changed after recording."""


@dataclass(frozen=True, slots=True)
class FeedbackOutcome:
    """Receipt and whether feedback was newly recorded."""

    receipt: SessionFeedbackReceipt
    created: bool


@dataclass(frozen=True, slots=True)
class _StoredFeedback:
    """Internal record of accepted learner feedback."""

    request: SessionFeedbackRequest
    receipt: SessionFeedbackReceipt


class SessionFeedbackStore:
    """
    Store one feedback record per completed coding session.

    This is an in-memory development implementation.

    Guarantees within one application process:
    - Feedback requires a completed session.
    - One feedback record per session.
    - Identical retries are idempotent.
    - Conflicting retries are rejected.
    - Concurrent requests are serialized.
    """

    def __init__(
        self,
        completion_store: SessionCompletionStore,
    ) -> None:
        self._completion_store = completion_store

        self._records: dict[str, _StoredFeedback] = {}
        self._lock = asyncio.Lock()

    async def record(
        self,
        request: SessionFeedbackRequest,
    ) -> FeedbackOutcome:
        """
        Record feedback for a completed session.

        The accepted request is preserved for safe retries.
        """

        async with self._lock:
            existing = self._records.get(request.session_id)

            if existing is not None:
                if existing.request == request:
                    return FeedbackOutcome(
                        receipt=existing.receipt.model_copy(deep=True),
                        created=False,
                    )

                raise SessionFeedbackAlreadyRecorded(
                    "This session already has different feedback."
                )

            completion = await self._completion_store.get_receipt(
                request.session_id
            )

            if completion is None:
                raise SessionNotCompleted(
                    "Feedback is allowed only after session completion."
                )

            receipt = SessionFeedbackReceipt(
                session_id=request.session_id,
                status="RECORDED",
                recorded_at=datetime.now(timezone.utc),
            )

            self._records[request.session_id] = _StoredFeedback(
                request=request.model_copy(deep=True),
                receipt=receipt.model_copy(deep=True),
            )

            return FeedbackOutcome(
                receipt=receipt,
                created=True,
            )
