from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.core.config import Settings
from app.llm.factory import create_llm_provider
from app.llm.provider import LLMProvider


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize and clean up shared application resources."""

    settings = Settings()
    provider = create_llm_provider(settings.llm_provider)

    app.state.llm_provider = provider

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
