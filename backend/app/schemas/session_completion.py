from datetime import datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.schemas.agent import ProgrammingLanguage


class CompletionMode(StrEnum):
    """How the learner finished the coding session."""

    EXTERNAL_JUDGE = "EXTERNAL_JUDGE"
    WITHOUT_SUBMISSION = "WITHOUT_SUBMISSION"


class JudgeVerdict(StrEnum):
    """User-reported verdict from an external online judge."""

    ACCEPTED = "ACCEPTED"
    WRONG_ANSWER = "WRONG_ANSWER"
    TIME_LIMIT_EXCEEDED = "TIME_LIMIT_EXCEEDED"
    MEMORY_LIMIT_EXCEEDED = "MEMORY_LIMIT_EXCEEDED"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    COMPILATION_ERROR = "COMPILATION_ERROR"
    PRESENTATION_ERROR = "PRESENTATION_ERROR"
    OUTPUT_LIMIT_EXCEEDED = "OUTPUT_LIMIT_EXCEEDED"
    OTHER = "OTHER"


class SessionCompletionRequest(BaseModel):
    """Information submitted when a learner ends a session."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(
        min_length=1,
        max_length=128,
    )

    code_revision: int = Field(ge=0)

    # Preserve the actual source problem and final code.
    problem_text: str = Field(
        min_length=1,
        max_length=20_000,
    )

    final_code: str = Field(
        max_length=40_000,
    )

    language: ProgrammingLanguage

    completion_mode: CompletionMode

    # Required only when an external result was reported.
    judge_verdict: JudgeVerdict | None = None

    # Optional learner-provided notes.
    notes: str | None = Field(
        default=None,
        max_length=2_000,
    )

    @field_validator(
        "session_id",
        "problem_text",
    )
    @classmethod
    def reject_blank_required_fields(
        cls,
        value: str,
    ) -> str:
        if not value.strip():
            raise ValueError(
                "Required text must not be blank."
            )

        return value

    @field_validator("notes")
    @classmethod
    def reject_blank_notes(
        cls,
        value: str | None,
    ) -> str | None:
        if value is not None and not value.strip():
            raise ValueError(
                "Notes must not be blank."
            )

        return value

    @model_validator(mode="after")
    def validate_completion_mode(self) -> Self:
        """Prevent contradictory submission information."""

        if self.completion_mode == CompletionMode.EXTERNAL_JUDGE:
            if self.judge_verdict is None:
                raise ValueError(
                    "An external judge result is required."
                )

            if not self.final_code.strip():
                raise ValueError(
                    "Submitted sessions require final code."
                )

        elif self.completion_mode == CompletionMode.WITHOUT_SUBMISSION:
            if self.judge_verdict is not None:
                raise ValueError(
                    "A non-submitted session cannot have a judge verdict."
                )

        return self


class SessionCompletionReceipt(BaseModel):
    """
    Server-generated confirmation of a completed session.

    The verdict source explicitly distinguishes a manually
    reported result from an automated judging result.
    """

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(
        min_length=1,
        max_length=128,
    )

    code_revision: int = Field(ge=0)

    completion_mode: CompletionMode

    judge_verdict: JudgeVerdict | None = None

    verdict_source: Literal["USER_REPORTED"] | None = None

    completed_at: datetime

    @field_validator("completed_at")
    @classmethod
    def require_timezone(
        cls,
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "Completion timestamp must include a timezone."
            )

        return value

    @model_validator(mode="after")
    def validate_verdict_source(self) -> Self:
        """Ensure the verdict is always attributed correctly."""

        if self.completion_mode == CompletionMode.EXTERNAL_JUDGE:
            if self.judge_verdict is None:
                raise ValueError(
                    "An external verdict is required."
                )

            if self.verdict_source != "USER_REPORTED":
                raise ValueError(
                    "External verdicts must be marked USER_REPORTED."
                )

        elif self.completion_mode == CompletionMode.WITHOUT_SUBMISSION:
            if (
                self.judge_verdict is not None
                or self.verdict_source is not None
            ):
                raise ValueError(
                    "A non-submitted session must not have a verdict."
                )

        return self
