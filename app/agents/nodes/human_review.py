from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field

from app.agents.llm import get_llm
from app.agents.routing import expand_with_dependents, next_nodes
from app.agents.state import AgentName, TravelState
from app.core.config import get_settings


class RevisionPlan(BaseModel):
    agents_to_rerun: list[AgentName] | None = Field(default_factory=list)


HumanReviewTarget = Literal[
    "final_response", "flight", "train", "hotel", "weather", "budget", "itinerary"
]


async def human_review_node(state: TravelState) -> Command[HumanReviewTarget]:
    decision = interrupt(
        {
            "type": "itinerary_review",
            "trip_constraints": state.get("trip_constraints"),
            "flight": state.get("flight_results"),
            "train": state.get("train_results"),
            "itinerary": state.get("itinerary_plan"),
            "budget": state.get("budget_analysis"),
            "revision_count": state.get("revision_count", 0),
        }
    )
    # decision = {"action": "approve" | "request_changes", "feedback": "..."}

    if decision.get("action") == "approve":
        return Command(goto="final_response", update={"review_status": "approved"})

    if state.get("revision_count", 0) >= get_settings().max_revisions:
        return Command(goto="final_response", update={"review_status": "max_revisions"})

    plan: RevisionPlan = (
        await get_llm()
        .with_structured_output(RevisionPlan)
        .ainvoke(
            [
                SystemMessage(
                    "Given the user's change request, choose which agents must re-run: "
                    "flight, train, hotel, weather, budget, itinerary. Choose the minimum."
                ),
                HumanMessage(decision.get("feedback") or ""),
            ]
        )
    )
    agents = expand_with_dependents(plan.agents_to_rerun or ["itinerary"])
    return Command(
        goto=next_nodes(agents, after_stage=-1),
        update={
            "selected_agents": agents,
            "feedback": decision.get("feedback"),
            "revision_count": state.get("revision_count", 0) + 1,
            "review_status": "changes_requested",
            "llm_calls": 1,
        },
    )
