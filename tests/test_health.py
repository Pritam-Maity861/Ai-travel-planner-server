import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.api.v1.router import api_router
from app.schemas.trip import ReviewRequest


@pytest.fixture
def test_app():
    # App without lifespan (so no external Postgres / MCP needed for basic API routing checks)
    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")
    return app


@pytest.mark.asyncio
async def test_health_check(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


def test_review_request_validation():
    # Approved requires no feedback
    valid_approve = ReviewRequest(action="approve")
    assert valid_approve.action == "approve"

    # Request changes requires feedback
    with pytest.raises(ValidationError):
        ReviewRequest(action="request_changes")

    valid_changes = ReviewRequest(action="request_changes", feedback="Please find cheaper hotels")
    assert valid_changes.feedback == "Please find cheaper hotels"
