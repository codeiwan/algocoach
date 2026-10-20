from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.agents.graph import create_analysis_graph
from app.api.analysis import router as analysis_router
from app.core.config import Settings
from app.llm.factory import create_llm_provider
from app.llm.provider import LLMProvider


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize and clean up shared application resources."""

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

    # Shared resources are initialized once at application startup.
    app.state.llm_provider = provider
    app.state.analysis_graph = create_analysis_graph(provider)

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

app.include_router(analysis_router)


@app.get("/api/v1/health")
async def health_check() -> dict[str, str]:
    """Return the current API health status."""

    return {"status": "ok"}


@app.get("/api/v1/dev/mock")
async def mock_provider_check(request: Request) -> dict[str, str]:
    """Verify that the Mock LLM Provider is available."""

    provider: LLMProvider = request.app.state.llm_provider

    response = await provider.generate(
        "AlgoCoach connection test"
    )

    return {
        "provider": "mock",
        "response": response,
    }
