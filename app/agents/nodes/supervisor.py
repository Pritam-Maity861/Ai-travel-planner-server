from datetime import date

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from app.agents.llm import get_llm
from app.agents.prompts import SUPERVISOR_PROMPT
from app.agents.routing import next_nodes
from app.agents.state import AgentName, TravelState, TripConstraints


class SupervisorDecision(BaseModel):
    selected_agents: list[AgentName]
    trip_constraints: TripConstraints
    reasoning: str


async def supervisor_node(state: TravelState) -> dict:
    seed_c = state.get("trip_constraints") or {}
    llm = get_llm().with_structured_output(SupervisorDecision)
    prompt_content = f"User Request: {state['user_query']}"
    if seed_c:
        prompt_content += f"\nPre-configured Constraints: {seed_c}"

    decision: SupervisorDecision = await llm.ainvoke(
        [
            SystemMessage(SUPERVISOR_PROMPT.format(today=date.today().isoformat())),
            HumanMessage(prompt_content),
        ]
    )

    merged_constraints = decision.trip_constraints.model_dump()
    for k, v in seed_c.items():
        if v is not None and (k not in merged_constraints or merged_constraints[k] is None):
            merged_constraints[k] = v

    # Ensure total travelers is accurate: adults + children
    adults = merged_constraints.get("adults") or 1
    children = merged_constraints.get("children") or 0
    merged_constraints["travelers"] = adults + children

    selected = list(decision.selected_agents)
    # If budget is tight, train mentioned, or rail transit provides major savings, add train
    budget_val = merged_constraints.get("budget")
    travelers_cnt = merged_constraints.get("travelers") or 1
    query_lower = state["user_query"].lower()

    rail_keywords = [
        "train", "rail", "railway", "vande bharat", "rajdhani", "shatabdi", "express", "tight"
    ]
    if "train" not in selected:
        if any(w in query_lower for w in rail_keywords):
            selected.append("train")
        elif budget_val and (budget_val / max(travelers_cnt, 1)) <= 25000:
            selected.append("train")

    return {
        "selected_agents": selected,
        "trip_constraints": merged_constraints,
        "supervisor_reasoning": decision.reasoning,
        "llm_calls": 1,
    }


def route_after_supervisor(state: TravelState) -> list[str]:
    return next_nodes(state["selected_agents"], after_stage=-1)
