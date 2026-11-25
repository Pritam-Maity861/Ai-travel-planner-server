from app.agents.routing import expand_with_dependents, next_nodes


def test_full_plan_fans_out_stage_one():
    sel = ["flight", "hotel", "weather", "budget", "itinerary"]
    assert set(next_nodes(sel, -1)) == {"flight", "hotel", "weather"}
    assert next_nodes(sel, 0) == ["budget"]
    assert next_nodes(sel, 1) == ["itinerary"]
    assert next_nodes(sel, 2) == ["human_review"]


def test_only_weather_selected_goes_straight_to_review():
    assert next_nodes(["weather"], -1) == ["weather"]
    assert next_nodes(["weather"], 0) == ["human_review"]


def test_hotel_change_reruns_budget_and_itinerary():
    assert set(expand_with_dependents(["hotel"])) == {"hotel", "budget", "itinerary"}


def test_flight_change_reruns_budget_and_itinerary():
    assert set(expand_with_dependents(["flight"])) == {"flight", "budget", "itinerary"}


def test_budget_change_reruns_itinerary():
    assert set(expand_with_dependents(["budget"])) == {"budget", "itinerary"}
