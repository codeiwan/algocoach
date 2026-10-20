from fastapi import FastAPI


app = FastAPI(
    title="AlgoCoach API",
    description="Backend API for AlgoCoach",
    version="0.1.0",
)


@app.get("/api/v1/health")
async def health_check() -> dict[str, str]:
    """Return the current API health status."""
    return {"status": "ok"}
