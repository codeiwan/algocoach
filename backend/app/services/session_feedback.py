import asyncio
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.schemas.session_feedback import (
    SessionFeedbackReceipt,
    SessionFeedbackRequest,
)
from app.services.session_completions import (
    SessionCompletionStore,
)


class SessionNotCompleted(Exception):
    """Raised when feedback is sent for an incomplete session."""


class SessionFeedbackAlreadyRecorded(Exception):
    """Raised when an existing feedback record is changed."""


@dataclass(frozen=True, slots=True)
class FeedbackOutcome:
    """Receipt and whether feedback was newly recorded."""

    receipt: SessionFeedbackReceipt
    created: bool


class SessionFeedbackStore:
    """
    Persist one feedback record per completed coding session.

    The completion store and feedback store share one SQLite DB.

    Guarantees:
    - Feedback requires an existing completion record.
    - One feedback record per session ID.
    - Identical retries return the original receipt.
    - Conflicting retries are rejected.
    - Records survive application restarts.
    - Concurrent writers are protected by SQLite transactions.
    """

    def __init__(
        self,
        completion_store: SessionCompletionStore,
    ) -> None:
        self._db_path: Path = completion_store.db_path
        self._lock = asyncio.Lock()

        self._initialize_database()

    def _connect(self) -> sqlite3.Connection:
        """Open a connection to the shared session database."""

        return sqlite3.connect(
            self._db_path,
            timeout=10.0,
        )

    def _initialize_database(self) -> None:
        """Create the feedback table if it does not exist."""

        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS session_feedback (
                    session_id TEXT PRIMARY KEY,
                    request_json TEXT NOT NULL,
                    receipt_json TEXT NOT NULL
                )
                """
            )
            connection.commit()

    async def record(
        self,
        request: SessionFeedbackRequest,
    ) -> FeedbackOutcome:
        """
        Persist learner-reported coaching feedback.

        The same transaction checks existing feedback,
        verifies session completion, and inserts a new record.
        """

        async with self._lock:
            with closing(self._connect()) as connection:
                with connection:
                    connection.execute("BEGIN IMMEDIATE")

                    # ------------------------------------------
                    # 1. Check for an existing feedback record.
                    # ------------------------------------------

                    row = connection.execute(
                        """
                        SELECT request_json, receipt_json
                        FROM session_feedback
                        WHERE session_id = ?
                        """,
                        (request.session_id,),
                    ).fetchone()

                    if row is not None:
                        original_request = (
                            SessionFeedbackRequest.model_validate_json(
                                row[0]
                            )
                        )

                        if original_request != request:
                            raise SessionFeedbackAlreadyRecorded(
                                "This session already has "
                                "different feedback."
                            )

                        original_receipt = (
                            SessionFeedbackReceipt.model_validate_json(
                                row[1]
                            )
                        )

                        return FeedbackOutcome(
                            receipt=original_receipt,
                            created=False,
                        )

                    # ------------------------------------------
                    # 2. Verify that the session was completed.
                    # ------------------------------------------

                    completed = connection.execute(
                        """
                        SELECT 1
                        FROM session_completions
                        WHERE session_id = ?
                        """,
                        (request.session_id,),
                    ).fetchone()

                    if completed is None:
                        raise SessionNotCompleted(
                            "Feedback is allowed only after "
                            "session completion."
                        )

                    # ------------------------------------------
                    # 3. Generate the server receipt.
                    # ------------------------------------------

                    receipt = SessionFeedbackReceipt(
                        session_id=request.session_id,
                        status="RECORDED",
                        recorded_at=datetime.now(timezone.utc),
                    )

                    # ------------------------------------------
                    # 4. Persist feedback and receipt atomically.
                    # ------------------------------------------

                    connection.execute(
                        """
                        INSERT INTO session_feedback (
                            session_id,
                            request_json,
                            receipt_json
                        )
                        VALUES (?, ?, ?)
                        """,
                        (
                            request.session_id,
                            request.model_dump_json(),
                            receipt.model_dump_json(),
                        ),
                    )

                    return FeedbackOutcome(
                        receipt=receipt,
                        created=True,
                    )
