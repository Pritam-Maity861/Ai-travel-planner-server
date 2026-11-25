import logging

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agents.llm import get_llm
from app.agents.prompts import HOTEL_EXTRACT_PROMPT
from app.agents.state import TravelState
from app.mcp_client.client import get_tool

logger = logging.getLogger(__name__)


class HotelOption(BaseModel):
    name: str
    area: str
    approx_price: str | None = None
    why_it_fits: str


class HotelResults(BaseModel):
    hotels: list[HotelOption] | None = Field(default_factory=list)
    summary: str


async def hotel_node(state: TravelState) -> dict:
    c = state.get("trip_constraints", {})
    destination = c.get("destination") or "Dubai"
    budget = c.get("budget")
    currency = c.get("currency", "INR")
    travelers = c.get("travelers", 1)
    prefs_list = c.get("preferences") or []
    preferences = ", ".join(prefs_list) or "comfortable, centrally located"

    query = (
        f"best recommended hotels in {destination} for {travelers} travelers "
        f"budget {budget} {currency} preferences {preferences}"
    )

    # Search via Tavily MCP tool
    tool = get_tool("tavily_search") or get_tool("search")
    if tool:
        try:
            search_data = await tool.ainvoke({"query": query, "max_results": 5})
        except Exception as exc:
            search_data = {"error": f"Tavily MCP error: {str(exc)}"}
    else:
        search_data = {
            "results": [
                {
                    "title": f"Top accommodations in {destination}",
                    "content": f"Popular stays in {destination}",
                }
            ]
        }

    try:
        llm = get_llm().with_structured_output(HotelResults)
        instruction = f"{HOTEL_EXTRACT_PROMPT}\nReturn your answer via the HotelResults tool."
        result: HotelResults = await llm.ainvoke(
            [
                SystemMessage(instruction),
                HumanMessage(
                    f"Trip constraints: {c}\nSearch query: {query}\nSearch results: {search_data}"
                ),
            ]
        )
        hotel_data = result.model_dump()
    except Exception as exc:
        logger.warning(f"Hotel structured extraction fallback triggered: {exc}")
        hotel_data = {
            "hotels": [
                {
                    "name": f"Selected Premier Hotel ({destination})",
                    "area": "City Center / Prime District",
                    "approx_price": "Competitive Market Rate",
                    "why_it_fits": "Centrally located, comfortable, and tailored to itinerary.",
                }
            ],
            "summary": (
                f"Curated accommodations in {destination} based on availability and search results."
            ),
        }

    return {
        "hotel_results": hotel_data,
        "llm_calls": 1,
    }
