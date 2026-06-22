"""Task definitions wiring each agent to a concrete deliverable.

Tasks run sequentially; later tasks receive earlier outputs as context, so the
itinerary, budget, and final plan build on the research below them.
"""

from __future__ import annotations

from crewai import Agent, Task


def build_tasks(agents: dict[str, Agent]) -> list[Task]:
    research_task = Task(
        description=(
            "Research a {duration_days}-day trip to {destination} "
            "(traveling from {origin}) for {travelers} traveler(s) interested in "
            "{interests}. Cover: best timing around {start_date}, entry/safety "
            "notes, key neighbourhoods/areas, and how to get there from {origin}. "
            "Extra traveler notes: {notes}. Use your tools; flag anything that "
            "should be reconfirmed closer to the trip."
        ),
        expected_output=(
            "A concise research brief with sections: Overview, Best Time To Go, "
            "Getting There, Areas To Base In, and Things To Reconfirm."
        ),
        agent=agents["researcher"],
    )

    logistics_task = Task(
        description=(
            "Plan the logistics for the {duration_days}-day {destination} trip. "
            "Use flight_estimate for the {origin}→{destination} distance/duration, "
            "find_lodging to suggest where to base, and weather_lookup for the "
            "season near {start_date}. Cover local transport and how to get around, "
            "a packing list tuned to {interests}, and recommended areas to stay. "
            "Consider notes: {notes}."
        ),
        expected_output=(
            "Sections: Getting There, Where To Stay, Getting Around, "
            "Weather & Best Daily Timing, and a bulleted Packing List."
        ),
        agent=agents["logistics"],
        context=[research_task],
    )

    experiences_task = Task(
        description=(
            "Curate the best experiences in {destination} for travelers into "
            "{interests}. Include signature must-dos, standout food/drink, and a "
            "few lesser-known local gems. Respect any constraints in {notes} "
            "(dietary, accessibility, etc.)."
        ),
        expected_output=(
            "Sections: Signature Experiences, Food & Drink, and Hidden Gems — each "
            "as a short annotated list with why it's worth it."
        ),
        agent=agents["curator"],
        context=[research_task],
    )

    itinerary_task = Task(
        description=(
            "Design a day-by-day itinerary for {duration_days} days in "
            "{destination} at a {pace} pace, drawing on the research, logistics, "
            "and curated experiences. Group activities geographically, include "
            "morning/afternoon/evening blocks with rough timings and meal ideas, "
            "and add a wet-weather alternative where useful."
        ),
        expected_output=(
            "A 'Day 1 … Day N' itinerary in Markdown, each day with "
            "Morning / Afternoon / Evening and a one-line daily theme."
        ),
        agent=agents["architect"],
        context=[research_task, logistics_task, experiences_task],
    )

    budget_task = Task(
        description=(
            "Estimate costs for the {duration_days}-day {destination} trip for "
            "{travelers} traveler(s) against the budget '{budget}'. Use "
            "flight_estimate for travel from {origin}, find_lodging to ground "
            "accommodation costs, web_search to sanity-check current prices, and "
            "currency_convert to localise totals where helpful. Itemise transport, "
            "lodging, food, activities, and local transport. Give low/typical/"
            "splurge ranges and money-saving tips, and state clearly whether the "
            "plan fits the budget."
        ),
        expected_output=(
            "A cost table or itemised list with per-category ranges, a total range "
            "(note the currency), a verdict on budget fit, and 3-5 savings tips."
        ),
        agent=agents["budget"],
        context=[itinerary_task],
    )

    budget_fit_task = Task(
        description=(
            "Produce the FINAL, budget-aligned day-by-day itinerary for the "
            "{duration_days}-day {destination} trip for {travelers} traveler(s), "
            "reconciling the draft itinerary with the budget analysis against the "
            "target budget '{budget}'. Where the plan exceeds the budget, swap "
            "pricey activities or meals for high-value cheaper alternatives, adjust "
            "dining tiers, or trim gently — without gutting the experience. Where it "
            "sits comfortably under budget, suggest optional upgrades the traveler "
            "can opt into. Preserve the {pace} pace and the geographic grouping so "
            "days still flow. Annotate every day with an estimated cost for "
            "{travelers} traveler(s) and keep a running total that lands within the "
            "stated budget — or, if the budget is genuinely infeasible, state the "
            "closest realistic total and what drives it."
        ),
        expected_output=(
            "A revised 'Day 1 … Day N' Markdown itinerary, each day with "
            "Morning / Afternoon / Evening, a one-line theme, and an Est. cost line, "
            "followed by a Trip Total that reconciles with the budget and a one-line "
            "note on how it fits (under / on / over, and by how much)."
        ),
        agent=agents["architect"],
        context=[itinerary_task, budget_task],
    )

    compile_task = Task(
        description=(
            "Combine all prior work into one polished trip plan for {destination} "
            "in clean Markdown. Open with a short, warm overview. Then include: "
            "Trip Snapshot (destination, dates, travelers, pace, budget), the "
            "FINAL budget-aligned day-by-day Itinerary (keep its per-day cost "
            "estimates and trip total), Experiences & Food highlights, Logistics & "
            "Packing, a Budget summary that matches the itinerary's total, and a "
            "final 'Before You Go' checklist. Use the budget-aligned itinerary as "
            "the single source of truth for the schedule, and remove any duplication "
            "or contradictions between the specialists' inputs."
        ),
        expected_output=(
            "A single, well-structured Markdown trip plan ready to hand to the "
            "traveler, with clear headings, per-day costs, a budget that reconciles "
            "with the itinerary total, and no internal contradictions."
        ),
        agent=agents["concierge"],
        context=[
            research_task,
            logistics_task,
            experiences_task,
            budget_fit_task,
            budget_task,
        ],
    )

    return [
        research_task,
        logistics_task,
        experiences_task,
        itinerary_task,
        budget_task,
        budget_fit_task,
        compile_task,
    ]
