import operator
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

AgentName = Literal["flight", "train", "hotel", "weather", "budget", "itinerary"]


class TripConstraints(BaseModel):
    origin: str | None = None
    destination: str | None = None
    start_date: str | None = None  # ISO date (e.g. 2026-11-25)
    end_date: str | None = None  # ISO date (e.g. 2026-12-02)
    duration_days: int | None = None
    travelers: int | None = 1
    adults: int | None = 1
    children: int | None = 0
    budget: float | None = None
    currency: str | None = "INR"
    food_preference: str | None = None  # veg, non-veg, vegan, jain, halal, any
    preferences: list[str] | None = Field(default_factory=list)


class TravelState(TypedDict, total=False):
    user_query: str
    guardrail_passed: bool
    blocked_reason: str | None

    # supervisor output
    selected_agents: list[str]
    trip_constraints: dict
    supervisor_reasoning: str

    # specialist outputs
    flight_results: dict
    train_results: dict
    hotel_results: dict
    weather_info: dict
    budget_analysis: dict
    itinerary_plan: dict

    # human-in-the-loop
    review_status: str  # pending | approved | changes_requested | max_revisions
    feedback: str | None
    revision_count: int

    final_response: str

    # reducers: safe for parallel nodes writing at the same time
    messages: Annotated[list[AnyMessage], add_messages]
    llm_calls: Annotated[int, operator.add]
