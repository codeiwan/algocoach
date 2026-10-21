from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from app.schemas.agent import ProgrammingLanguage


class ConversationTurn(BaseModel):
    """One previous user or assistant message."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)

    @field_validator("content")
    @classmethod
    def nonblank_content(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Message must not be blank.")

        return value


class CoachingQuestionRequest(BaseModel):
    """A question grounded in the current solving context."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=128)
    code_revision: int = Field(ge=0)

    problem_text: str = Field(min_length=1, max_length=20000)
    current_code: str = Field(max_length=40000)
    language: ProgrammingLanguage

    question: str = Field(min_length=1, max_length=1000)

    # A recent coaching message shown by the frontend.
    latest_coaching: str | None = Field(
        default=None,
        max_length=3000,
    )

    # Short conversation history, provided by the frontend.
    history: list[ConversationTurn] = Field(
        default_factory=list,
        max_length=6,
    )

    @field_validator(
        "session_id",
        "problem_text",
        "question",
    )
    @classmethod
    def nonblank_required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(
                "Required text must not be blank."
            )

        return value

    @field_validator("latest_coaching")
    @classmethod
    def normalize_optional_text(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        return value.strip() or None


class CoachingQuestionResponse(BaseModel):
    """A coaching answer, not an execution or judge verdict."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    answered_revision: int = Field(ge=0)
    answer: str = Field(min_length=1, max_length=8000)
