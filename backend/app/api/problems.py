from fastapi import APIRouter, Request

from app.llm.provider import LLMProvider
from app.schemas.problem import (
    ProblemStructureRequest,
    StructuredProblem,
)


router = APIRouter(
    prefix="/api/v1/dev/problems",
    tags=["Development"],
)


@router.post("/structure", response_model=StructuredProblem)
async def structure_problem(
    problem_request: ProblemStructureRequest,
    request: Request,
) -> StructuredProblem:
    """Structure a coding problem using the configured LLM."""

    provider: LLMProvider = request.app.state.llm_provider

    return await provider.structure_problem(problem_request)
