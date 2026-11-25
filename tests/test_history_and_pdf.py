import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import SessionLocal
from app.main import create_app
from app.models.conversation import Conversation
from app.repositories.conversation_repository import ConversationRepository


@pytest.mark.asyncio
async def test_trip_history_and_pdf_persistence_workflow():
    app = create_app()
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Register a user
            user_email = f"traveler_{uuid.uuid4().hex[:6]}@test.com"
            reg_resp = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": user_email,
                    "password": "SecretPassword123!",
                    "name": "Jordan Wanderer",
                },
            )
            assert reg_resp.status_code == 201
            auth_header = {"Authorization": f"Bearer {reg_resp.json()['access_token']}"}
            user_id = uuid.UUID(reg_resp.json()["user"]["id"])

            # 2. Directly seed a completed conversation for testing history and PDF
            conv_id = uuid.uuid4()
            async with SessionLocal() as session:
                repo = ConversationRepository(session)
                conv = Conversation(
                    id=conv_id,
                    user_id=user_id,
                    title="Trip to Ladakh",
                    destination="Ladakh",
                    user_query="Plan a 6 day trip to Ladakh",
                    status="completed",
                    final_response="## 6-Day Ladakh Adventure\nEnjoy the Pangong Tso lake.",
                )
                session.add(conv)
                await session.commit()

            # 3. List trips for authenticated user
            history_resp = await client.get("/api/v1/trips", headers=auth_header)
            assert history_resp.status_code == 200
            trips = history_resp.json()
            assert len(trips) >= 1
            matched = next((t for t in trips if t["thread_id"] == str(conv_id)), None)
            assert matched is not None
            assert matched["destination"] == "Ladakh"
            assert matched["has_pdf"] is False

            # 4. Synthesize state in LangGraph checkpointer for conv_id
            state_data = {
                "user_query": "Plan a 6 day trip to Ladakh",
                "trip_constraints": {
                    "origin": "Delhi",
                    "destination": "Ladakh",
                    "duration_days": 6,
                    "travelers": 2,
                    "budget": 50000,
                    "currency": "INR",
                },
                "itinerary_plan": {
                    "destination": "Ladakh",
                    "duration_days": 6,
                    "daily_plans": [
                        {
                            "day": 1,
                            "title": "Arrival in Leh",
                            "morning": "Acclimatize at hotel",
                            "afternoon": "Stroll around Leh Market",
                            "evening": "Shanti Stupa sunset",
                        }
                    ],
                },
                "final_response": "Full confirmed travel plan for Ladakh.",
            }
            await app.state.graph.aupdate_state(
                {"configurable": {"thread_id": str(conv_id)}},
                state_data,
            )

            # 5. Call preview-pdf endpoint -> in-memory preview
            preview_resp = await client.get(
                f"/api/v1/trips/{conv_id}/preview-pdf",
                headers=auth_header,
            )
            assert preview_resp.status_code == 200
            assert preview_resp.headers["content-type"] == "application/pdf"
            assert preview_resp.content.startswith(b"%PDF")

            # Verify that preview-pdf did NOT persist pdf_data to DB
            async with SessionLocal() as session:
                repo = ConversationRepository(session)
                db_conv = await repo.get(conv_id)
                assert db_conv.pdf_data is None

            # 6. Call download-pdf endpoint -> compiles, persists to DB, and returns PDF bytes
            pdf_resp = await client.get(
                f"/api/v1/trips/{conv_id}/pdf",
                headers=auth_header,
            )
            assert pdf_resp.status_code == 200
            assert pdf_resp.headers["content-type"] == "application/pdf"
            assert pdf_resp.content.startswith(b"%PDF")

            # Verify that pdf_data IS NOW permanently stored in DB
            async with SessionLocal() as session:
                repo = ConversationRepository(session)
                db_conv = await repo.get(conv_id)
                assert db_conv.pdf_data is not None
                assert len(db_conv.pdf_data) > 1000
                assert "Ladakh" in db_conv.pdf_filename

            # 7. Re-check history list -> has_pdf is now True
            history_after = await client.get("/api/v1/trips", headers=auth_header)
            all_after = history_after.json()
            matched_after = next((t for t in all_after if t["thread_id"] == str(conv_id)), None)
            assert matched_after["has_pdf"] is True
