import uuid

from app.services.pdf_service import generate_trip_pdf


def test_generate_trip_pdf():
    mock_state = {
        "trip_constraints": {
            "origin": "Kolkata",
            "destination": "Dubai",
            "start_date": "2026-12-01",
            "duration_days": 4,
            "travelers": 2,
            "budget": 80000,
            "currency": "INR",
            "preferences": ["luxury", "foodie"],
        },
        "flight_results": {
            "dep_iata": "CCU",
            "arr_iata": "DXB",
            "summary": "Direct and connecting flight routes available from CCU to DXB.",
            "raw": {
                "flights": [
                    {
                        "airline": "Emirates",
                        "flight": "EK571",
                        "departure": "2026-12-01T09:45:00",
                        "arrival": "2026-12-01T13:30:00",
                    }
                ]
            },
        },
        "hotel_results": {
            "summary": "Curated accommodations located in Downtown and Marina.",
            "hotels": [
                {
                    "name": "Rove Downtown",
                    "area": "Downtown Dubai",
                    "approx_price": "8,500 INR/night",
                    "why_it_fits": "Central, great views, within budget.",
                }
            ],
        },
        "weather_info": {
            "summary": "Pleasant and sunny weather expected with temperatures between 22C and 28C."
        },
        "itinerary_plan": {
            "days": [
                {
                    "day": 1,
                    "title": "Arrival & Marina Walk",
                    "morning": "Touchdown at DXB and check-in to Rove Downtown.",
                    "afternoon": "Stroll around Dubai Marina Promenade.",
                    "evening": "Dine at Pier 7 with skyline views.",
                    "transport_notes": "Use Dubai Metro Red Line.",
                }
            ],
            "tips": ["Buy a Silver Nol card for metro transit.", "Carry sun protection."],
        },
        "budget_analysis": {
            "flights_estimate": 35000,
            "hotel_estimate": 25000,
            "food_and_transport_estimate": 12000,
            "activities_estimate": 8000,
            "total_estimate": 80000,
            "within_budget": True,
            "recommendations": ["Book metro passes in advance."],
            "assumptions": ["Economy flights booked 3 weeks prior."],
        },
        "final_response": "# Dubai Travel Plan\nComplete verified itinerary.",
    }

    thread_id = str(uuid.uuid4())
    pdf_bytes = generate_trip_pdf(mock_state, thread_id)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")


def test_generate_trip_pdf_with_list_raw_flights_and_preview():
    # Case where AviationStack / MCP tool returns flights as a raw list
    mock_state = {
        "trip_constraints": {
            "origin": "Kolkata",
            "destination": "Dubai",
            "duration_days": 4,
            "travelers": 2,
            "budget": 80000,
        },
        "flight_results": {
            "summary": "Direct flights available.",
            "raw": [
                {
                    "airline": "FlyDubai",
                    "flight": "FZ442",
                    "departure": "10:00",
                    "arrival": "14:00",
                }
            ],
        },
        "budget_analysis": {
            "total_estimate": 75000,
            "within_budget": True,
        },
        "itinerary_plan": {
            "days": [
                {
                    "day": 1,
                    "title": "Arrival",
                    "morning": "Check in",
                    "afternoon": "Rest",
                    "evening": "Dinner",
                }
            ]
        },
    }

    thread_id = str(uuid.uuid4())
    pdf_bytes = generate_trip_pdf(mock_state, thread_id, is_preview=True)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")


def test_generate_trip_pdf_with_markdown_table_and_unicode_hyphens():
    # User's exact case with markdown table, unicode hyphens \u2011, arrows \u279c, bullets
    user_markdown = (
        "IndiGo – Kolkata (CCU) ➜ Pakyong (IXR)\n\n"
        "| Date (Local) | Flight # | Departure (UTC) | Arrival (UTC) |\n"
        "|--------------|----------|-----------------|---------------|\n"
        "| 22 Nov 2026 | 6E 7467 | 19:55 | 21:10 |\n"
        "| 22 Nov 2026 | 6E 7465 | 17:40 | 18:55 |\n"
        "| 23 Nov 2026 | 6E 7461 | 06:55 | 08:15 |\n\n"
        "Key points for your 7\u2011day, 8\u2011traveller trip:\n"
        "* All available options are operated by IndiGo.\n"
        "* The earliest departure is 06:55 UTC on 23 Nov (flight 6E\u20117461) – good.\n"
        "* No price information was supplied.\n\n"
        "Choose the flight that best fits your itinerary."
    )

    mock_state = {
        "trip_constraints": {
            "origin": "Kolkata",
            "destination": "North Sikkim",
            "duration_days": 7,
            "travelers": 8,
            "budget": 80000,
            "currency": "INR",
        },
        "flight_results": {
            "summary": user_markdown,
            "raw": [],
        },
        "itinerary_plan": {
            "days": [
                {
                    "day": 1,
                    "title": "Gangtok Arrival",
                    "morning": "Arrive and transfer",
                    "afternoon": "Hotel check-in",
                    "evening": "MG Marg walk",
                }
            ]
        },
        "budget_analysis": {
            "total_estimate": 80000,
            "within_budget": True,
        },
    }

    thread_id = str(uuid.uuid4())
    pdf_bytes = generate_trip_pdf(mock_state, thread_id, is_preview=True)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")


def test_generate_trip_pdf_with_rupee_symbol_and_joined_br_bullets():
    """Verify that rupee signs, approx, and joined br bullets format cleanly without tofu boxes."""
    from app.services.pdf_service import clean_markdown_for_pdf

    sample_budget = "Budget ₹80,000 for 8 travelers ≈ ₹10,000 per person) ≈ ₹200-₹300 per person"
    cleaned = clean_markdown_for_pdf(sample_budget)
    assert "₹" not in cleaned
    assert "≈" not in cleaned
    assert "INR" in cleaned
    assert "~" in cleaned

    sample_tips = (
        "• Sturdy, waterproof trekking boots (broken-in) <br>"
        "• Lightweight camp shoes/sandals for evenings"
    )

    mock_state = {
        "trip_constraints": {
            "origin": "Kolkata",
            "destination": "North Sikkim",
            "duration_days": 7,
            "travelers": 8,
            "budget": 80000,
            "currency": "₹",
        },
        "flight_results": {
            "summary": "Flights Kolkata to Bagdogra / Pakyong",
            "raw": [],
        },
        "itinerary_plan": {
            "days": [
                {
                    "day": 1,
                    "title": "Arrival in Gangtok",
                    "morning": "Fly to IXB/IXR <br> Transfer to Gangtok",
                    "afternoon": "Hotel check-in and briefing",
                    "evening": "Stroll MG Marg",
                }
            ],
            "tips": [sample_tips],
        },
        "budget_analysis": {
            "total_estimate": 80000,
            "within_budget": True,
            "recommendations": [sample_budget],
            "assumptions": ["Permits ≈ ₹200-₹300 per person"],
        },
    }

    thread_id = str(uuid.uuid4())
    pdf_bytes = generate_trip_pdf(mock_state, thread_id, is_preview=True)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")



def test_generate_trip_pdf_with_train_and_preferences():
    mock_state = {
        "trip_constraints": {
            "origin": "Kolkata",
            "destination": "North Sikkim",
            "start_date": "2026-12-05",
            "end_date": "2026-12-12",
            "duration_days": 7,
            "travelers": 8,
            "adults": 6,
            "children": 2,
            "budget": 80000,
            "currency": "INR",
            "food_preference": "Vegetarian",
        },
        "flight_results": {
            "summary": "Flights available to Bagdogra (IXB) starting at INR 4,800/seat.",
        },
        "train_results": {
            "origin": "Kolkata",
            "destination": "New Jalpaiguri",
            "start_date": "2026-12-05",
            "summary": (
                "| Train # | Name | Departure | Arrival | 3A Fare | SL Fare |\n"
                "|---------|------|-----------|---------|---------|---------|\n"
                "| 12377 | Padatik Express | 23:20 | 09:15 | INR 1,120 | INR 420 |\n"
                "| 22301 | Vande Bharat | 05:55 | 13:25 | INR 1,565 | - |\n"
                "Budget Savings: Taking Padatik Express saves INR 24,000 for "
                "8 passengers vs flights."
            ),
        },
        "itinerary_plan": {
            "days": [
                {
                    "day": 1,
                    "title": "Board Train from Howrah / Sealdah",
                    "morning": "Prepare luggage and packing for mountain terrain.",
                    "afternoon": "Leisure afternoon in Kolkata.",
                    "evening": "Board overnight Padatik Express (23:20). Vegetarian dinner served.",
                    "transport_notes": "Overnight train transit to NJP.",
                }
            ],
            "tips": ["Pure Vegetarian meals available at all major stops.", "Carry warm layers."],
        },
        "budget_analysis": {
            "flights_estimate": 38400,
            "trains_estimate": 8960,
            "hotel_estimate": 28000,
            "food_and_transport_estimate": 14000,
            "activities_estimate": 6000,
            "total_estimate": 56960,
            "within_budget": True,
            "recommendations": ["Choosing train transit keeps entire tour well within 80,000 INR."],
            "assumptions": ["6 adults + 2 children traveling together."],
        },
    }

    thread_id = str(uuid.uuid4())
    pdf_bytes = generate_trip_pdf(mock_state, thread_id, is_preview=False)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 2000
    assert pdf_bytes.startswith(b"%PDF")
