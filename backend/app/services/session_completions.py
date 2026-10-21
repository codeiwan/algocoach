import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

from app.schemas.session_completion import (
    CompletionMode,
    SessionCompletionReceipt,
    SessionCompletionRequest,
)


class SessionAlreadyCompleted(Exception):
    """Raised when a completed session receives conflicting data."""


@dataclass(frozen=True, slots=True)
class CompletionOutcome:
    """Receipt and whether it was newly created."""

    receipt: SessionCompletionReceipt
    created: bool


@dataclass(frozen=True, slots=True)
class _StoredCompletion:
    """Internal immutable completion record."""

    request: SessionCompletionRequest
    receipt: SessionCompletionReceipt


class SessionCompletionStore:
    """
    Store session completion records in application memory.

    Guarantees within one process:
    - One completion per session ID.
    - Identical retries return the existing receipt.
    - Conflicting retries are rejected.
    - Concurrent requests are serialized.
    """

    def __init__(self) -> None:
        self._records: dict[str, _StoredCompletion] = {}
        self._lock = asyncio.Lock()

    async def complete(
        self,
        request: SessionCompletionRequest,
    ) -> CompletionOutcome:
        """Create or return an existing completion record."""

        async with self._lock:
            existing = self._records.get(request.session_id)

            if existing is not None:
                if existing.request == request:
                    return CompletionOutcome(
                        receipt=existing.receipt.model_copy(deep=True),
                        created=False,
                    )

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

            self._records[request.session_id] = _StoredCompletion(
                request=request.model_copy(deep=True),
                receipt=receipt.model_copy(deep=True),
            )

            return CompletionOutcome(
                receipt=receipt,
                created=True,
            )

    async def get_receipt(
        self,
        session_id: str,
    ) -> SessionCompletionReceipt | None:
        """
        Return a completion receipt if this session is finished.

        A deep copy prevents callers from mutating stored data.
        """

        async with self._lock:
            record = self._records.get(session_id)

            if record is None:
                return None

            return record.receipt.model_copy(deep=True)
