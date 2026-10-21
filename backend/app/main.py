from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.agents.graph import create_analysis_graph
from app.api.analysis import router as analysis_router
from app.api.coaching_question import (
    router as coaching_question_router,
)
from app.api.hints import router as hints_router
from app.api.problems import router as problems_router
from app.api.session_completion import (
    router as session_completion_router,
)
from app.api.session_feedback import (
    router as session_feedback_router,
)
from app.api.submission import router as submission_router
from app.core.config import Settings
from app.llm.factory import create_llm_provider
from app.llm.provider import LLMProvider
from app.services.hint_sessions import HintSessionStore
from app.services.session_completions import (
    SessionCompletionStore,
)
from app.services.session_feedback import (
    SessionFeedbackStore,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize and clean up application resources."""

    settings = Settings()

    api_key = (
        settings.openai_api_key.get_secret_value()
        if settings.openai_api_key is not None
        else None
    )

    provider = create_llm_provider(
        settings.llm_provider,
        api_key=api_key,
        model=settings.openai_model,
    )

    app.state.llm_provider = provider

    # Existing LangGraph code analysis.
    app.state.analysis_graph = create_analysis_graph(
        provider
    )

    # Progressive hint records.
    app.state.hint_session_store = HintSessionStore()

    # Session completion records.
    completion_store = SessionCompletionStore()

    app.state.session_completion_store = completion_store

    # Feedback shares the completion database.
    app.state.session_feedback_store = SessionFeedbackStore(
        completion_store=completion_store,
    )

    try:
        yield
    finally:
        await provider.aclose()


app = FastAPI(
    title="AlgoCoach API",
    description="Backend API for AlgoCoach",
    version="0.1.0",
    lifespan=lifespan,
)


# --------------------------------------------------
# API routers
# --------------------------------------------------

app.include_router(analysis_router)
app.include_router(problems_router)
app.include_router(hints_router)
app.include_router(submission_router)
app.include_router(session_completion_router)
app.include_router(session_feedback_router)
app.include_router(coaching_question_router)


# --------------------------------------------------
# Health check
# --------------------------------------------------

@app.get("/api/v1/health")
async def health_check() -> dict[str, str]:
    """Return the current API health status."""

    return {"status": "ok"}


# --------------------------------------------------
# Legacy development endpoint
# --------------------------------------------------

@app.get("/api/v1/dev/mock")
async def mock_provider_check(
    request: Request,
) -> dict[str, str]:
    """Legacy development endpoint for text generation testing."""

    provider: LLMProvider = request.app.state.llm_provider

    response = await provider.generate(
        "AlgoCoach connection test"
    )

    return {
        "provider": "mock",
        "response": response,
    }
