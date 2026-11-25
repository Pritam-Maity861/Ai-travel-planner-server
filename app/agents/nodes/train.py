import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.llm import get_llm
from app.agents.prompts import TRAIN_SUMMARY_PROMPT
from app.agents.state import TravelState
from app.mcp_client.client import get_tool

logger = logging.getLogger(__name__)


async def train_node(state: TravelState) -> dict:
    c = state.get("trip_constraints", {})
    origin = c.get("origin") or "Kolkata"
    destination = c.get("destination") or "Siliguri / New Jalpaiguri"
    start_date = c.get("start_date") or "Next Available Date"
    adults = c.get("adults") or 1
    children = c.get("children") or 0
    total_travelers = c.get("travelers") or (adults + children)
    budget = c.get("budget")
    currency = c.get("currency") or "INR"
    food_pref = c.get("food_preference") or "Any / Standard"

    # Step 1: Query Train Intelligence Tool (Find My Train MCP / World Train Map)
    tool = (
        get_tool("search_train_routes")
        or get_tool("search_routes")
        or get_tool("fallback_train_routes")
    )
    train_data = None
    if tool:
        try:
            if tool.name == "search_routes":
                train_data = await tool.ainvoke({"query": f"{origin} to {destination}"})
            else:
                train_data = await tool.ainvoke(
                    {
                        "origin": origin,
                        "destination": destination,
                        "date": start_date,
                    }
                )
        except Exception as exc:
            logger.warning(f"Train tool error: {exc}")
            fallback = get_tool("fallback_train_routes")
            if fallback:
                train_data = await fallback.ainvoke(
                    {
                        "origin": origin,
                        "destination": destination,
                        "date": start_date,
                    }
                )
            else:
                train_data = {"error": f"Train MCP error: {str(exc)}"}

    if not train_data:
        train_data = {
            "origin": origin,
            "destination": destination,
            "departure_date": start_date,
            "note": "Querying verified railway schedules and regional express corridors.",
        }

    # Step 2: Analyze & Summarize with LLM
    llm = get_llm()
    summary_resp = await llm.ainvoke(
        [
            SystemMessage(TRAIN_SUMMARY_PROMPT),
            HumanMessage(
                f"Sector: {origin} to {destination}\n"
                f"Departure Date: {start_date}\n"
                f"Party: {adults} Adults, {children} Children ({total_travelers} total)\n"
                f"Budget: {budget} {currency}\n"
                f"Food Preference: {food_pref}\n"
                f"Train Availability Data: {train_data}"
            ),
        ]
    )

    return {
        "train_results": {
            "origin": origin,
            "destination": destination,
            "start_date": start_date,
            "raw": train_data,
            "summary": summary_resp.content,
        },
        "llm_calls": 1,
    }
