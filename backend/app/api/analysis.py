from fastapi import APIRouter, HTTPException, Request

from app.schemas.agent import AnalysisRequest, AnalysisResult


router = APIRouter(
    prefix="/api/v1/dev",
    tags=["Development"],
)


@router.post("/analyze", response_model=AnalysisResult)
async def analyze_code(
    analysis_request: AnalysisRequest,
    request: Request,
) -> AnalysisResult:
    """Run the LangGraph analysis workflow."""

    graph = request.app.state.analysis_graph

    final_state = await graph.ainvoke(
        {"request": analysis_request}
    )

    result: AnalysisResult = final_state["result"]

    # Ensure that the result belongs to the requested code revision.
    if result.analyzed_revision != analysis_request.code_revision:
        raise HTTPException(
            status_code=500,
            detail="Analysis revision mismatch.",
        )

    return result
