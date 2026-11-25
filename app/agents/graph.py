from langgraph.graph import END, START, StateGraph

from app.agents.nodes.budget import budget_node, route_after_budget
from app.agents.nodes.final_response import final_response_node
from app.agents.nodes.flight import flight_node
from app.agents.nodes.guardrail import blocked_node, guardrail_node, route_after_guardrail
from app.agents.nodes.hotel import hotel_node
from app.agents.nodes.human_review import human_review_node
from app.agents.nodes.itinerary import itinerary_node
from app.agents.nodes.supervisor import route_after_supervisor, supervisor_node
from app.agents.nodes.train import train_node
from app.agents.nodes.weather import weather_node
from app.agents.routing import next_nodes
from app.agents.state import TravelState


async def collect_node(state: TravelState) -> dict:
    return {}  # join point after parallel stage (flight, train, hotel, weather)


def route_after_collect(state: TravelState) -> list[str]:
    return next_nodes(state.get("selected_agents", []), after_stage=0)


def build_graph(checkpointer=None):
    g = StateGraph(TravelState)

    g.add_node("guardrail", guardrail_node)
    g.add_node("blocked", blocked_node)
    g.add_node("supervisor", supervisor_node)
    g.add_node("flight", flight_node)
    g.add_node("train", train_node)
    g.add_node("hotel", hotel_node)
    g.add_node("weather", weather_node)
    g.add_node("collect", collect_node)
    g.add_node("budget", budget_node)
    g.add_node("itinerary", itinerary_node)
    g.add_node("human_review", human_review_node)
    g.add_node("final_response", final_response_node)

    g.add_edge(START, "guardrail")
    g.add_conditional_edges(
        "guardrail",
        route_after_guardrail,
        {"supervisor": "supervisor", "blocked": "blocked"},
    )
    g.add_edge("blocked", END)

    g.add_conditional_edges("supervisor", route_after_supervisor)
    for n in ("flight", "train", "hotel", "weather"):
        g.add_edge(n, "collect")

    g.add_conditional_edges("collect", route_after_collect)
    g.add_conditional_edges("budget", route_after_budget)
    g.add_edge("itinerary", "human_review")
    # human_review routes dynamically via Command(goto=...)
    g.add_edge("final_response", END)

    return g.compile(checkpointer=checkpointer)
