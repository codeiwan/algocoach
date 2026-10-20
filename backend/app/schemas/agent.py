from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProgressStatus(StrEnum):
    """Current stage of the user's problem-solving process."""

    UNDERSTANDING = "UNDERSTANDING"
    IMPLEMENTING = "IMPLEMENTING"
    DEBUGGING = "DEBUGGING"
    STUCK_SUSPECTED = "STUCK_SUSPECTED"
    REVIEWING = "REVIEWING"


class IssueSeverity(StrEnum):
    """Severity of a potential code issue."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AnalysisRequest(BaseModel):
    """Snapshot of the problem and code to be analyzed."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1)
    code_revision: int = Field(ge=0)

    problem_text: str = Field(min_length=1)
    current_code: str
    previous_code: str | None = None


class CodeIssue(BaseModel):
    """A potential issue identified during code analysis."""

    model_config = ConfigDict(extra="forbid")

    category: Literal[
        "logic",
        "complexity",
        "edge_case",
        "constraint",
    ]

    severity: IssueSeverity
    description: str = Field(min_length=1)
    evidence: str = Field(min_length=1)

    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_line_range(self) -> Self:
        """Validate that the referenced code range is consistent."""

        if (self.line_start is None) != (self.line_end is None):
            raise ValueError(
                "line_start and line_end must be provided together."
            )

        if (
            self.line_start is not None
            and self.line_end is not None
            and self.line_start > self.line_end
        ):
            raise ValueError(
                "line_start must be less than or equal to line_end."
            )

        return self


class AnalysisResult(BaseModel):
    """Structured analysis returned by the Agent system."""

    model_config = ConfigDict(extra="forbid")

    analyzed_revision: int = Field(ge=0)

    algorithm: str | None = None
    progress_status: ProgressStatus

    summary: str = Field(min_length=1)
    positive_observation: str | None = None
    complexity_estimate: str | None = None

    issues: list[CodeIssue] = Field(default_factory=list)
