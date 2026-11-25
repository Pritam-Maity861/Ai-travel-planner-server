from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from app.agents.llm import get_llm
from app.agents.prompts import GUARDRAIL_PROMPT
from app.agents.state import TravelState


class GuardrailResult(BaseModel):
    allowed: bool
    category: Literal["travel_planning", "off_topic", "unsafe", "invalid"]
    reason: str


async def guardrail_node(state: TravelState) -> dict:
    llm = get_llm().with_structured_output(GuardrailResult)
    result: GuardrailResult = await llm.ainvoke(
        [SystemMessage(GUARDRAIL_PROMPT), HumanMessage(state["user_query"])]
    )
    return {
        "guardrail_passed": result.allowed,
        "blocked_reason": None if result.allowed else result.reason,
        "llm_calls": 1,
    }


async def blocked_node(state: TravelState) -> dict:
    reason = state.get("blocked_reason") or "This request can't be processed."
    return {"final_response": reason}


def route_after_guardrail(state: TravelState) -> str:
    return "supervisor" if state.get("guardrail_passed") else "blocked"
