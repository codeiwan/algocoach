from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class ProblemStructureRequest(BaseModel):
    """Raw coding problem text submitted by the user."""

    model_config = ConfigDict(extra="forbid")

    problem_text: str = Field(
        min_length=1,
        max_length=20_000,
    )

    @field_validator("problem_text")
    @classmethod
    def validate_problem_text(cls, value: str) -> str:
        """Reject whitespace-only problem statements."""

        if not value.strip():
            raise ValueError(
                "Problem text must not be empty."
            )

        return value


class ProblemExample(BaseModel):
    """An input/output example found in the source problem."""

    model_config = ConfigDict(extra="forbid")

    input: str
    output: str
    explanation: str | None


class StructuredProblem(BaseModel):
    """Structured representation of a coding-test problem."""

    model_config = ConfigDict(extra="forbid")

    # Use null when the source does not provide a title.
    title: str | None

    # Concise explanation of the actual task.
    goal: str = Field(min_length=1)

    # Use null when an input/output section is absent.
    input_format: str | None
    output_format: str | None

    # Preserve constraints explicitly supported by the source.
    constraints: list[str]

    # Include only examples provided in the original problem.
    examples: list[ProblemExample]

    # Record unclear or missing information without inventing it.
    ambiguities: list[str]
