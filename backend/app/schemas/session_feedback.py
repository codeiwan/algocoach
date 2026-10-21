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


class CoachingOutcome(StrEnum):
    """Learner-reported assessment of AI coaching quality."""

    ACCURATE_AND_HELPFUL = "ACCURATE_AND_HELPFUL"
    ACCURATE_BUT_NOT_HELPFUL = "ACCURATE_BUT_NOT_HELPFUL"
    MISLEADING_OR_INCORRECT = "MISLEADING_OR_INCORRECT"
    NOT_USED = "NOT_USED"
    UNABLE_TO_ASSESS = "UNABLE_TO_ASSESS"


class MainChallenge(StrEnum):
    """
    Legacy learning-difficulty categories.

    Retained temporarily for Stage 4.6 client compatibility.
    """

    UNDERSTANDING = "UNDERSTANDING"
    ALGORITHM = "ALGORITHM"
    IMPLEMENTATION = "IMPLEMENTATION"
    DEBUGGING = "DEBUGGING"
    COMPLEXITY = "COMPLEXITY"
    OTHER = "OTHER"


class SessionFeedbackRequest(BaseModel):
    """
    Learner-reported feedback after session completion.

    During the UI transition, two request formats are accepted:

    1. New: coaching_outcome
    2. Legacy: difficulty_rating

    The new coaching-quality flow does not require a difficulty
    rating or user-satisfaction score.
    """

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(
        min_length=1,
        max_length=128,
    )

    # New primary feedback signal.
    coaching_outcome: CoachingOutcome | None = None

    # Optional details about incorrect coaching or other issues.
    comment: str | None = Field(
        default=None,
        max_length=1000,
    )

    # --------------------------------------------------
    # Legacy fields
    #
    # Kept temporarily to avoid breaking the existing
    # Stage 4.6 frontend during the Stage 4.7 migration.
    # New clients should not send these fields.
    # --------------------------------------------------

    difficulty_rating: int | None = Field(
        default=None,
        ge=1,
        le=5,
        strict=True,
    )

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

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, value: str) -> str:
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
        if value is None:
            return None

        normalized = value.strip()

        return normalized or None

    @model_validator(mode="after")
    def validate_feedback_content(self) -> Self:
        """
        Require a meaningful feedback signal.

        New clients provide coaching_outcome.
        Legacy clients provide difficulty_rating.

        Never fabricate a difficulty score for new feedback.
        """

        if (
            self.coaching_outcome is None
            and self.difficulty_rating is None
        ):
            raise ValueError(
                "Provide coaching_outcome or legacy "
                "difficulty_rating."
            )

        return self


class SessionFeedbackReceipt(BaseModel):
    """Confirmation returned after feedback is recorded."""

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
        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                "Feedback timestamp must include a timezone."
            )

        return value
