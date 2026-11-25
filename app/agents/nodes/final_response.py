from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agents.llm import get_llm
from app.agents.prompts import FINAL_RESPONSE_PROMPT
from app.agents.state import TravelState


async def final_response_node(state: TravelState) -> dict:
    llm = get_llm()

    context = (
        f"Trip Constraints: {state.get('trip_constraints')}\n"
        f"Flight Results: {state.get('flight_results', {}).get('summary', 'N/A')}\n"
        f"Train Results (WorldTrainMap): {state.get('train_results', {}).get('summary', 'N/A')}\n"
        f"Hotel Results: {state.get('hotel_results', {}).get('summary', 'N/A')}\n"
        f"Weather Info: {state.get('weather_info', {}).get('summary', 'N/A')}\n"
        f"Budget Analysis: {state.get('budget_analysis')}\n"
        f"Itinerary Plan: {state.get('itinerary_plan')}\n"
        f"Review Status: {state.get('review_status', 'approved')}\n"
    )

    result = await llm.ainvoke(
        [
            SystemMessage(FINAL_RESPONSE_PROMPT),
            HumanMessage(context),
        ]
    )

    return {
        "final_response": result.content,
        "messages": [AIMessage(result.content)],
        "llm_calls": 1,
    }
