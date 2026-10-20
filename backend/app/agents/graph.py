from typing import NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph

from app.llm.provider import LLMProvider
from app.schemas.agent import AnalysisRequest, AnalysisResult


class AnalysisGraphState(TypedDict):
    """State shared between LangGraph nodes."""

    request: AnalysisRequest
    result: NotRequired[AnalysisResult]


def create_analysis_graph(provider: LLMProvider):
    """Build and compile the analysis workflow."""

    async def analyze_node(
        state: AnalysisGraphState,
    ) -> dict[str, AnalysisResult]:
        """Analyze the current problem-solving snapshot."""

        request = state["request"]
        result = await provider.analyze(request)

        return {"result": result}

    builder = StateGraph(AnalysisGraphState)

    builder.add_node("analyze", analyze_node)

    builder.add_edge(START, "analyze")
    builder.add_edge("analyze", END)

    return builder.compile()
