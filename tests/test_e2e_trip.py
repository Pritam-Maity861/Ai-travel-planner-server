from uuid import uuid4

from starlette.testclient import TestClient

from app.main import app


def get_auth_headers(client: TestClient) -> dict[str, str]:
    email = f"e2e_{uuid4().hex[:6]}@example.com"
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "name": "E2E Tester"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_trip_requires_authentication():
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/trips",
            json={"query": "Plan a trip to Paris"},
        )
        assert resp.status_code == 401


def test_guardrail_blocks_offtopic():
    with TestClient(app) as client:
        headers = get_auth_headers(client)
        resp = client.post(
            "/api/v1/trips",
            json={"query": "Write me a Python sorting algorithm"},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "blocked"
        assert data["message"] is not None
        print("\n[Guardrail Test Passed]:", data)


def test_get_nonexistent_trip():
    with TestClient(app) as client:
        fake_id = uuid4()
        resp = client.get(f"/api/v1/trips/{fake_id}")
        assert resp.status_code == 404


def test_full_trip_workflow_and_approval():
    with TestClient(app) as client:
        headers = get_auth_headers(client)
        # Step 1: Create trip request
        create_resp = client.post(
            "/api/v1/trips",
            json={
                "query": "Plan a 4 day trip to Dubai for next month from Kolkata, budget 80000 INR"
            },
            headers=headers,
        )
        assert create_resp.status_code == 201
        trip_data = create_resp.json()
        thread_id = trip_data["thread_id"]
        assert trip_data["status"] == "awaiting_review"
        assert trip_data["review_payload"] is not None
        print("\n[Trip Awaiting Review]:", trip_data["status"], "Thread:", thread_id)

        # Step 2: Approve the trip
        review_resp = client.post(
            f"/api/v1/trips/{thread_id}/review",
            json={"action": "approve"},
            headers=headers,
        )
        assert review_resp.status_code == 200
        final_data = review_resp.json()
        assert final_data["status"] == "completed"
        assert final_data["message"] is not None
        print("\n[Final Plan Generated]:", final_data["status"])
