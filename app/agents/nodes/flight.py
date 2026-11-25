from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agents.llm import get_llm
from app.agents.prompts import FLIGHT_IATA_PROMPT, FLIGHT_SUMMARY_PROMPT
from app.agents.state import TravelState
from app.mcp_client.client import get_tool


class IataCodes(BaseModel):
    dep: str = Field(description="3-letter IATA code for departure")
    arr: str = Field(description="3-letter IATA code for arrival")


async def flight_node(state: TravelState) -> dict:
    c = state.get("trip_constraints", {})
    origin = c.get("origin") or "Kolkata"
    destination = c.get("destination") or "Dubai"

    llm = get_llm()

    # Step 1: Resolve IATA codes
    try:
        iata_llm = llm.with_structured_output(IataCodes)
        codes: IataCodes = await iata_llm.ainvoke(
            [
                SystemMessage(FLIGHT_IATA_PROMPT),
                HumanMessage(f"Origin city: {origin}, Destination city: {destination}"),
            ]
        )
        dep_iata = codes.dep.upper()
        arr_iata = codes.arr.upper()
    except Exception:
        dep_iata = "CCU"
        arr_iata = "DXB"

    # Step 2: Query Flights MCP Tool
    tool = get_tool("search_flights")
    if tool:
        try:
            flight_data = await tool.ainvoke(
                {"dep_iata": dep_iata, "arr_iata": arr_iata, "limit": 5}
            )
        except Exception as exc:
            flight_data = {"error": f"Flights tool error: {str(exc)}"}
    else:
        flight_data = {
            "dep": dep_iata,
            "arr": arr_iata,
            "note": "AviationStack MCP tool unavailable. Providing standard route estimates.",
        }

    # Step 3: Summarize
    summary_resp = await llm.ainvoke(
        [
            SystemMessage(FLIGHT_SUMMARY_PROMPT),
            HumanMessage(
                f"Trip constraints: {c}\n"
                f"Route: {dep_iata} -> {arr_iata}\n"
                f"Flight Data: {flight_data}"
            ),
        ]
    )

    return {
        "flight_results": {
            "dep_iata": dep_iata,
            "arr_iata": arr_iata,
            "raw": flight_data,
            "summary": summary_resp.content,
        },
        "llm_calls": 2,
    }
