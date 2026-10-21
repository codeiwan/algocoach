import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

from app.schemas.session_completion import (
    CompletionMode,
    SessionCompletionReceipt,
    SessionCompletionRequest,
)


class SessionAlreadyCompleted(Exception):
    """Raised when a finished session receives conflicting data."""


@dataclass(frozen=True, slots=True)
class CompletionOutcome:
    """Receipt plus information about whether it was newly created."""

    receipt: SessionCompletionReceipt
    created: bool


@dataclass(frozen=True, slots=True)
class _StoredCompletion:
    """Internal record of an accepted completion request."""

    request: SessionCompletionRequest
    receipt: SessionCompletionReceipt


class SessionCompletionStore:
    """
    Store session completions in application memory.

    Guarantees within one server process:
    - One completion record per session ID.
    - Identical retries return the same receipt.
    - Conflicting retries are rejected.
    - Concurrent requests are serialized.

    Records are lost when the server process restarts.
    """

    def __init__(self) -> None:
        self._records: dict[str, _StoredCompletion] = {}
        self._lock = asyncio.Lock()

    async def complete(
        self,
        request: SessionCompletionRequest,
    ) -> CompletionOutcome:
        """Create or return the immutable completion record."""

        async with self._lock:
            existing = self._records.get(request.session_id)

            if existing is not None:
                # An identical retry is safe and idempotent.
                if existing.request == request:
                    return CompletionOutcome(
                        receipt=existing.receipt.model_copy(deep=True),
                        created=False,
                    )

                # A completed session cannot be overwritten.
                raise SessionAlreadyCompleted(
                    "Session completion already exists "
                    "with different information."
                )

            verdict_source = (
                "USER_REPORTED"
                if request.completion_mode
                == CompletionMode.EXTERNAL_JUDGE
                else None
            )

            receipt = SessionCompletionReceipt(
                session_id=request.session_id,
                code_revision=request.code_revision,
                completion_mode=request.completion_mode,
                judge_verdict=request.judge_verdict,
                verdict_source=verdict_source,
                completed_at=datetime.now(timezone.utc),
            )

            # Preserve the original accepted request for
            # idempotency checks and future session records.
            self._records[request.session_id] = _StoredCompletion(
                request=request.model_copy(deep=True),
                receipt=receipt.model_copy(deep=True),
            )

            return CompletionOutcome(
                receipt=receipt,
                created=True,
            )
