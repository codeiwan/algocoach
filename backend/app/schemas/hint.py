
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.agent import ProgrammingLanguage


class HintLevel(StrEnum):
    """Progressive levels of coding-test guidance."""

    DIRECTION = "DIRECTION"
    ALGORITHM = "ALGORITHM"
    IMPLEMENTATION = "IMPLEMENTATION"


class HintSource(StrEnum):
    """How a hint was requested."""

    USER_REQUEST = "USER_REQUEST"
    AUTOMATIC = "AUTOMATIC"


class HintRequest(BaseModel):
    """Context provided to an LLM for hint generation."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1)
    code_revision: int = Field(ge=0)

    problem_text: str = Field(min_length=1)
    current_code: str
    language: ProgrammingLanguage

    level: HintLevel

    previous_hints: list[str] = Field(
        default_factory=list,
        max_length=3,
    )


class NextHintRequest(BaseModel):
    """Public API request without a client-controlled hint level."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=128)
    code_revision: int = Field(ge=0)

    problem_text: str = Field(min_length=1, max_length=20_000)
    current_code: str
    language: ProgrammingLanguage


class HintResult(BaseModel):
    """Structured guidance returned by the coaching system."""

    model_config = ConfigDict(extra="forbid")

    hinted_revision: int = Field(ge=0)
    level: HintLevel

    message: str = Field(min_length=1)
    code_reference: str | None = None
