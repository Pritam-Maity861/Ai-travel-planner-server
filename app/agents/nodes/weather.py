from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.llm import get_llm
from app.agents.prompts import WEATHER_SUMMARY_PROMPT
from app.agents.state import TravelState
from app.mcp_client.client import get_tool


async def weather_node(state: TravelState) -> dict:
    c = state.get("trip_constraints", {})
    destination = c.get("destination") or "Dubai"
    days = min(c.get("duration_days") or 7, 16)

    tool = get_tool("get_forecast")
    if tool:
        try:
            forecast = await tool.ainvoke({"city": destination, "days": days})
        except Exception as exc:
            forecast = {"error": f"Weather tool error: {str(exc)}"}
    else:
        forecast = {"error": "Weather MCP tool not loaded. Will provide climate overview."}

    summary = await get_llm().ainvoke(
        [
            SystemMessage(WEATHER_SUMMARY_PROMPT),
            HumanMessage(f"Trip constraints: {c}\nForecast data: {forecast}"),
        ]
    )

    return {
        "weather_info": {
            "destination": destination,
            "raw": forecast,
            "summary": summary.content,
        },
        "llm_calls": 1,
    }
