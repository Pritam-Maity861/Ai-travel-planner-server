import logging
import uuid
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.types import Command

from app.core.exceptions import TripNotAwaitingReview, TripNotFound
from app.db.session import SessionLocal
from app.repositories.conversation_repository import ConversationRepository
from app.schemas.trip import ReviewRequest, TripCreateRequest, TripHistoryItem, TripResponse
from app.services.pdf_service import generate_trip_pdf

logger = logging.getLogger(__name__)


class TripService:
    def __init__(self, graph, repo: ConversationRepository):
        self.graph = graph
        self.repo = repo

    @staticmethod
    def _config(conv_id: uuid.UUID) -> dict:
        return {"configurable": {"thread_id": str(conv_id)}}

    async def create_trip(
        self,
        request_or_query: TripCreateRequest | str,
        user_id: uuid.UUID | None = None,
    ) -> TripResponse:
        if isinstance(request_or_query, str):
            query = request_or_query
            thread_id = None
            initial_constraints = {}
        else:
            query = request_or_query.query
            thread_id = request_or_query.thread_id
            initial_constraints = {
                "origin": request_or_query.origin,
                "destination": request_or_query.destination,
                "start_date": request_or_query.start_date,
                "end_date": request_or_query.end_date,
                "adults": request_or_query.adults,
                "children": request_or_query.children,
                "travelers": request_or_query.adults + request_or_query.children,
                "budget": request_or_query.budget,
                "currency": request_or_query.currency,
                "food_preference": request_or_query.food_preference,
            }
            initial_constraints = {k: v for k, v in initial_constraints.items() if v is not None}

        conv = None
        if thread_id:
            conv = await self.repo.get(thread_id)
            if conv and user_id and conv.user_id != user_id:
                conv = None

        if conv:
            await self.repo.update_status(conv.id, status="running", user_query=query)
        else:
            conv = await self.repo.create(user_query=query, user_id=user_id)

        try:
            state_input: dict[str, Any] = {
                "user_query": query,
                "revision_count": 0,
                "messages": [HumanMessage(query)],
            }
            if initial_constraints:
                state_input["trip_constraints"] = initial_constraints

            await self.graph.ainvoke(
                state_input,
                self._config(conv.id),
            )
        except Exception as exc:
            logger.error(f"Error during graph execution for conv {conv.id}: {exc}")
            await self._safe_update_status(conv.id, status="failed")
            return TripResponse(
                thread_id=conv.id,
                status="failed",
                destination=initial_constraints.get("destination"),
                message=(
                    f"Planning session encountered an issue: {str(exc)}. "
                    "You can retry generation using this session or plan a new travel."
                ),
            )
        return await self._sync(conv)

    async def list_user_trips(self, user_id: uuid.UUID) -> list[TripHistoryItem]:
        convs = await self.repo.list_by_user(user_id)
        return [
            TripHistoryItem(
                thread_id=c.id,
                title=c.title or (
                    f"Trip to {c.destination}" if c.destination else "Custom Travel Plan"
                ),
                destination=c.destination,
                user_query=c.user_query,
                status=c.status,
                has_pdf=c.pdf_data is not None,
                created_at=c.created_at,
            )
            for c in convs
        ]

    async def review(self, conv_id: uuid.UUID, body: ReviewRequest) -> TripResponse:
        conv = await self.repo.get(conv_id)
        if not conv:
            raise TripNotFound()
        if conv.status != "awaiting_review":
            raise TripNotAwaitingReview()

        await self.graph.ainvoke(
            Command(resume={"action": body.action, "feedback": body.feedback}),
            self._config(conv_id),
        )

        resp = await self._sync(conv)

        # If user approved and reached completed status, compile and permanently store PDF in DB
        if body.action == "approve" and resp.status == "completed":
            snap = await self.graph.aget_state(self._config(conv_id))
            values = snap.values or {}
            try:
                pdf_bytes = generate_trip_pdf(values, str(conv_id), is_preview=False)
                dest = (values.get("trip_constraints") or {}).get("destination") or "Trip"
                filename = f"Aetheria_Master_Plan_{dest.replace(' ', '_')}_{str(conv_id)[:8]}.pdf"
                await self.repo.save_pdf(conv_id, pdf_bytes, filename)
                resp.has_pdf = True
                logger.info(
                    f"Generated and stored master PDF for conv {conv_id} ({len(pdf_bytes)} bytes)"
                )
            except Exception as e:
                logger.error(f"Failed to generate and store final PDF for conv {conv_id}: {e}")

        return resp

    async def get_trip(self, conv_id: uuid.UUID) -> TripResponse:
        conv = await self.repo.get(conv_id)
        if not conv:
            raise TripNotFound()
        return await self._sync(conv)

    async def preview_pdf(self, conv_id: uuid.UUID) -> bytes:
        conv = await self.repo.get(conv_id)
        if not conv:
            raise TripNotFound()
        snap = await self.graph.aget_state(self._config(conv_id))
        values = snap.values or {}
        return generate_trip_pdf(values, str(conv_id), is_preview=True)

    async def get_pdf(self, conv_id: uuid.UUID) -> tuple[bytes, str]:
        conv = await self.repo.get(conv_id)
        if not conv or not conv.pdf_data:
            raise TripNotFound("PDF document not found for this trip.")
        filename = conv.pdf_filename or f"Trip_{str(conv_id)[:8]}.pdf"
        return conv.pdf_data, filename

    async def delete_trip(self, conv_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        return await self.repo.delete(conv_id, user_id=user_id)

    async def _safe_update_status(self, conv_id: uuid.UUID, status: str) -> None:
        try:
            async with SessionLocal() as session:
                repo = ConversationRepository(session)
                await repo.update_status(conv_id, status=status)
        except Exception as e:
            logger.error(f"Could not safely update status for conv {conv_id}: {e}")

    async def _sync(self, conv) -> TripResponse:
        snap = await self.graph.aget_state(self._config(conv.id))
        values = snap.values or {}

        # Derive status
        if values.get("blocked_reason"):
            status = "blocked"
        elif snap.next:  # interrupted at human_review
            status = "awaiting_review"
        elif values.get("final_response"):
            status = "completed"
        elif values.get("guardrail_passed") is None:
            status = "running"
        else:
            status = "failed"

        # Extract title and destination from constraints if available
        constraints = values.get("trip_constraints") or {}
        dest = constraints.get("destination")
        title = f"Trip to {dest}" if dest else None

        # Build payload for awaiting_review
        review_payload = None
        if status == "awaiting_review":
            review_payload = {
                "type": "itinerary_review",
                "trip_constraints": constraints,
                "flight": values.get("flight_results"),
                "train": values.get("train_results"),
                "itinerary": values.get("itinerary_plan"),
                "budget": values.get("budget_analysis"),
                "revision_count": values.get("revision_count", 0),
            }

        message = values.get("final_response") or values.get("blocked_reason")

        # Persist updated status, title, and destination
        await self.repo.update_status(
            conv.id,
            status=status,
            title=title,
            destination=dest,
            final_response=values.get("final_response"),
            review_payload=review_payload,
            flight_results=values.get("flight_results"),
            hotel_results=values.get("hotel_results"),
            weather_info=values.get("weather_info"),
            budget_analysis=values.get("budget_analysis"),
            itinerary_plan=values.get("itinerary_plan"),
        )

        return TripResponse(
            thread_id=conv.id,
            status=status,
            title=title,
            destination=dest,
            has_pdf=conv.pdf_data is not None,
            message=message,
            review_payload=review_payload,
        )
