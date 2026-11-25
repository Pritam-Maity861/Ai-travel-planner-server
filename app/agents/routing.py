STAGES = [["flight", "train", "hotel", "weather"], ["budget"], ["itinerary"]]

# If an agent is re-run after user feedback, everything downstream must re-run too.
DEPENDENTS = {
    "flight": ["budget", "itinerary"],
    "train": ["budget", "itinerary"],
    "hotel": ["budget", "itinerary"],
    "weather": ["itinerary"],
    "budget": ["itinerary"],
    "itinerary": [],
}


def next_nodes(selected: list[str], after_stage: int = -1) -> list[str]:
    """Return the next node(s) to run, given selected agents and the last finished stage."""
    for i in range(after_stage + 1, len(STAGES)):
        picked = [a for a in STAGES[i] if a in selected]
        if picked:
            return picked  # several names => parallel fan-out
    return ["human_review"]


def expand_with_dependents(agents: list[str]) -> list[str]:
    result = set(agents)
    for a in agents:
        result.update(DEPENDENTS.get(a, []))
    return list(result)
