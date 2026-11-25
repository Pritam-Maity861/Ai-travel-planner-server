from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agents.llm import get_llm
from app.agents.prompts import BUDGET_PROMPT
from app.agents.routing import next_nodes
from app.agents.state import TravelState


class BudgetAnalysis(BaseModel):
    flights_estimate: float | None = Field(
        default=0.0,
        description="Estimated flight costs in trip currency, or 0 / null if traveling by train",
    )
    trains_estimate: float | None = Field(
        default=0.0,
        description="Estimated train transit costs if train option evaluated, or 0 / null",
    )
    hotel_estimate: float | None = Field(
        default=0.0,
        description="Estimated hotel costs in trip currency",
    )
    food_and_transport_estimate: float | None = Field(
        default=0.0,
        description="Food and local transport estimate",
    )
    activities_estimate: float | None = Field(
        default=0.0,
        description="Sightseeing and activities estimate",
    )
    total_estimate: float = Field(
        default=0.0,
        description="Sum of all estimated expenses",
    )
    within_budget: bool | None = Field(
        default=True,
        description="Whether within user budget, or null if unstated",
    )
    recommendations: list[str] | None = Field(
        default_factory=list,
        description="Tips to optimize cost, including train savings if budget is tight",
    )
    assumptions: list[str] | None = Field(
        default_factory=list,
        description="Cost assumptions made, including group breakdown",
    )


async def budget_node(state: TravelState) -> dict:
    c = state.get("trip_constraints", {})
    flight = state.get("flight_results", {})
    train = state.get("train_results", {})
    hotel = state.get("hotel_results", {})

    llm = get_llm().with_structured_output(BudgetAnalysis)
    result: BudgetAnalysis = await llm.ainvoke(
        [
            SystemMessage(BUDGET_PROMPT),
            HumanMessage(
                f"Trip constraints: {c}\n"
                f"Flight results: {flight.get('summary', 'Not selected/available')}\n"
                f"Train results: {train.get('summary', 'Not selected/available')}\n"
                f"Hotel results: {hotel.get('summary', 'Not selected/available')}"
            ),
        ]
    )

    return {
        "budget_analysis": result.model_dump(),
        "llm_calls": 1,
    }


def route_after_budget(state: TravelState) -> list[str]:
    return next_nodes(state.get("selected_agents", []), after_stage=1)
