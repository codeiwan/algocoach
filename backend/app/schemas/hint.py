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
    """Context provided to the hint generation system."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1)
    code_revision: int = Field(ge=0)

    problem_text: str = Field(min_length=1)
    current_code: str
    language: ProgrammingLanguage

    level: HintLevel

    # Previously delivered hints help avoid repetition.
    previous_hints: list[str] = Field(
        default_factory=list,
        max_length=3,
    )


class HintResult(BaseModel):
    """A structured hint produced by the coaching system."""

    model_config = ConfigDict(extra="forbid")

    hinted_revision: int = Field(ge=0)
    level: HintLevel

    message: str = Field(min_length=1)

    # Optional reference to a relevant portion of the code.
    code_reference: str | None = None
