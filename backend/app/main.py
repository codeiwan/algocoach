from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.llm.mock import MockLLMProvider
from app.llm.provider import LLMProvider


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize and clean up shared application resources."""
    provider: LLMProvider = MockLLMProvider()
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
    return {"status": "ok"}


@app.get("/api/v1/dev/mock")
async def mock_provider_check(request: Request) -> dict[str, str]:
    """Temporarily verify the Mock LLM Provider integration."""
    provider: LLMProvider = request.app.state.llm_provider

    response = await provider.generate("AlgoCoach connection test")

    return {
        "provider": "mock",
        "response": response,
    }