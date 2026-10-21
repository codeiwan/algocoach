from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class MainChallenge(StrEnum):
    """The learner's main difficulty during the session."""

    UNDERSTANDING = "UNDERSTANDING"
    ALGORITHM = "ALGORITHM"
    IMPLEMENTATION = "IMPLEMENTATION"
    DEBUGGING = "DEBUGGING"
    COMPLEXITY = "COMPLEXITY"
    OTHER = "OTHER"


class SessionFeedbackRequest(BaseModel):
    """Learner-reported feedback after completing a session."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(
        min_length=1,
        max_length=128,
    )

    # 1 = very easy, 5 = very difficult.
    difficulty_rating: int = Field(
        ge=1,
        le=5,
        strict=True,
    )

    # Optional: leave null when a feature was not used
    # or the learner does not wish to rate it.
    intervention_timing_rating: int | None = Field(
        default=None,
        ge=1,
        le=5,
        strict=True,
    )

    hint_helpfulness_rating: int | None = Field(
        default=None,
        ge=1,
        le=5,
        strict=True,
    )

    review_helpfulness_rating: int | None = Field(
        default=None,
        ge=1,
        le=5,
        strict=True,
    )

    main_challenge: MainChallenge | None = None

    comment: str | None = Field(
        default=None,
        max_length=1000,
    )

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, value: str) -> str:
        """Reject whitespace-only session identifiers."""

        if not value.strip():
            raise ValueError(
                "Session ID must not be blank."
            )

        return value

    @field_validator("comment")
    @classmethod
    def normalize_comment(
        cls,
        value: str | None,
    ) -> str | None:
        """Treat blank optional comments as omitted."""

        if value is None:
            return None

        normalized = value.strip()

        return normalized or None


class SessionFeedbackReceipt(BaseModel):
    """Confirmation returned after the feedback is recorded."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(
        min_length=1,
        max_length=128,
    )

    status: Literal["RECORDED"]

    recorded_at: datetime

    @field_validator("recorded_at")
    @classmethod
    def require_timezone(
        cls,
        value: datetime,
    ) -> datetime:
        """Use a timezone-aware server timestamp."""

        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                "Feedback timestamp must include a timezone."
            )

        return value
