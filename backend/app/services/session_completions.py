import asyncio
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.schemas.session_completion import (
    CompletionMode,
    SessionCompletionReceipt,
    SessionCompletionRequest,
)


class SessionAlreadyCompleted(Exception):
    """Raised when a completed session receives conflicting data."""


@dataclass(frozen=True, slots=True)
class CompletionOutcome:
    """Receipt and whether the completion was newly recorded."""

    receipt: SessionCompletionReceipt
    created: bool


class SessionCompletionStore:
    """
    Persist completed coding sessions in SQLite.

    Guarantees:
    - One completion per session ID.
    - Identical retries return the original receipt.
    - Conflicting retries are rejected.
    - Records survive application restarts.
    - SQLite transactions protect concurrent writers.

    Database location:
    - Default: backend/data/algocoach.sqlite3
    - Optional: custom db_path for testing

    Runtime data is excluded from Git using backend/data/.gitignore.
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
    ) -> None:
        # Resolve the backend directory from this source file.
        # This does not depend on the current working directory.
        backend_root = Path(__file__).resolve().parents[2]

        default_path = (
            backend_root
            / "data"
            / "algocoach.sqlite3"
        )

        self._db_path = Path(
            db_path if db_path is not None else default_path
        ).expanduser().resolve()

        self._db_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._lock = asyncio.Lock()

        self._initialize_database()

    def _connect(self) -> sqlite3.Connection:
        """Open a short-lived database connection."""

        return sqlite3.connect(
            self._db_path,
            timeout=10.0,
        )

    def _initialize_database(self) -> None:
        """Create the completion table if it does not exist."""

        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS session_completions (
                    session_id TEXT PRIMARY KEY,
                    request_json TEXT NOT NULL,
                    receipt_json TEXT NOT NULL
                )
                """
            )
            connection.commit()

    async def complete(
        self,
        request: SessionCompletionRequest,
    ) -> CompletionOutcome:
        """
        Create an immutable completion or return an identical one.

        BEGIN IMMEDIATE makes the read-compare-insert sequence
        atomic across SQLite connections and server processes.
        """

        async with self._lock:
            with closing(self._connect()) as connection:
                with connection:
                    connection.execute("BEGIN IMMEDIATE")

                    row = connection.execute(
                        """
                        SELECT request_json, receipt_json
                        FROM session_completions
                        WHERE session_id = ?
                        """,
                        (request.session_id,),
                    ).fetchone()

                    if row is not None:
                        original_request = (
                            SessionCompletionRequest.model_validate_json(
                                row[0]
                            )
                        )

                        if original_request != request:
                            raise SessionAlreadyCompleted(
                                "Session completion already exists "
                                "with different information."
                            )

                        original_receipt = (
                            SessionCompletionReceipt.model_validate_json(
                                row[1]
                            )
                        )

                        return CompletionOutcome(
                            receipt=original_receipt,
                            created=False,
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

                    connection.execute(
                        """
                        INSERT INTO session_completions (
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

                    return CompletionOutcome(
                        receipt=receipt,
                        created=True,
                    )

    async def get_receipt(
        self,
        session_id: str,
    ) -> SessionCompletionReceipt | None:
        """
        Retrieve a completed session's receipt.

        The feedback service uses this to verify that
        a session was completed before accepting feedback.
        """

        async with self._lock:
            with closing(self._connect()) as connection:
                row = connection.execute(
                    """
                    SELECT receipt_json
                    FROM session_completions
                    WHERE session_id = ?
                    """,
                    (session_id,),
                ).fetchone()

        if row is None:
            return None

        return SessionCompletionReceipt.model_validate_json(
            row[0]
        )
