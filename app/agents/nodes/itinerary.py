import logging

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agents.llm import get_llm
from app.agents.prompts import ITINERARY_PROMPT
from app.agents.state import TravelState

logger = logging.getLogger(__name__)


class DayPlan(BaseModel):
    day: int = Field(description="Day number, e.g. 1")
    title: str = Field(description="Day theme or title")
    morning: str = Field(description="Morning activity plan")
    afternoon: str = Field(description="Afternoon activity plan")
    evening: str = Field(description="Evening activity plan")
    transport_notes: str = Field(description="Transport recommendations for the day")


class ItineraryPlan(BaseModel):
    days: list[DayPlan] | None = Field(default_factory=list, description="Day-by-day plan")
    tips: list[str] | None = Field(
        default_factory=list, description="General travel tips and highlights"
    )


async def itinerary_node(state: TravelState) -> dict:
    c = state.get("trip_constraints", {})
    weather = state.get("weather_info", {})
    hotel = state.get("hotel_results", {})
    flight = state.get("flight_results", {})
    train = state.get("train_results", {})
    budget = state.get("budget_analysis", {})
    feedback = state.get("feedback")

    prompt_context = (
        f"Trip Constraints: {c}\n"
        f"Travel Party: {c.get('adults', 1)} Adults, {c.get('children', 0)} Children\n"
        f"Food Preference: {c.get('food_preference', 'Any / Standard')}\n"
        f"Weather Info: {weather.get('summary', 'Standard climate')}\n"
        f"Flight Options: {flight.get('summary', 'Direct/Connecting flight')}\n"
        f"Train Options (WorldTrainMap): {train.get('summary', 'Standard railway connection')}\n"
        f"Hotel Details: {hotel.get('summary', 'Selected hotels')}\n"
        f"Budget Breakdown: {budget}\n"
    )

    if feedback:
        prompt_context += f"\nUser Requested Revisions / Feedback: {feedback}\n"

    messages = [
        SystemMessage(ITINERARY_PROMPT),
        HumanMessage(prompt_context),
    ]

    try:
        llm = get_llm().with_structured_output(ItineraryPlan)
        result: ItineraryPlan = await llm.ainvoke(messages)
    except Exception as exc:
        logger.warning(
            f"Itinerary tool_use structured output failed, retrying with json_mode: {exc}"
        )
        json_prompt = (
            f"{ITINERARY_PROMPT}\n\n"
            "Return ONLY a valid JSON object matching this schema:\n"
            '{"days": [{"day": 1, "title": "...", "morning": "...", "afternoon": "...", '
            '"evening": "...", "transport_notes": "..."}], "tips": ["..."]}'
        )
        llm_json = get_llm().with_structured_output(ItineraryPlan, method="json_mode")
        result = await llm_json.ainvoke([SystemMessage(json_prompt), HumanMessage(prompt_context)])

    return {
        "itinerary_plan": result.model_dump(),
        "llm_calls": 1,
    }
