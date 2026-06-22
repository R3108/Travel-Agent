"""Agent definitions for the Trip Trailers crew.

Six specialists run sequentially. They all share one Google Gemini LLM
(via CrewAI's provider wrapper) and a pool of pluggable tools.
"""

from __future__ import annotations

from crewai import LLM, Agent

from ..config import get_settings
from .tools import (
    CurrencyTool,
    FlightEstimateTool,
    LodgingTool,
    PlacesTool,
    WeatherTool,
    WebSearchTool,
)


def build_llm() -> LLM:
    """Construct the shared LLM for every agent (provider set by MODEL)."""
    settings = get_settings()
    settings.export_provider_env()
    return LLM(
        model=settings.model,            # e.g. "openrouter/deepseek/deepseek-chat-v3.1:free"
        api_key=settings.llm_api_key or None,
        temperature=0.6,
        max_tokens=8000,
        timeout=120,
        # Free OpenRouter slugs are heavily rate-limited; litellm retries 429s
        # (and transient API errors) with exponential backoff before giving up.
        num_retries=5,
    )


def build_agents() -> dict[str, Agent]:
    """Create and return the named crew of agents."""
    llm = build_llm()
    web = WebSearchTool()
    weather = WeatherTool()
    places = PlacesTool()
    flights = FlightEstimateTool()
    lodging = LodgingTool()
    currency = CurrencyTool()

    common = dict(llm=llm, allow_delegation=False, verbose=True)

    researcher = Agent(
        role="Destination Research Specialist",
        goal=(
            "Build an accurate, current picture of {destination}: when to go, "
            "safety and entry notes, neighbourhoods, transport from {origin}, and "
            "what makes it special for travelers interested in {interests}."
        ),
        backstory=(
            "A meticulous travel researcher who has briefed thousands of trips. "
            "You separate evergreen facts from things that must be reconfirmed, "
            "and you always ground claims in what tools return or clearly flag "
            "them as general knowledge."
        ),
        tools=[web, places],
        **common,
    )

    logistics = Agent(
        role="Travel Logistics & Weather Coordinator",
        goal=(
            "Work out the practical backbone of the trip to {destination}: getting "
            "there and around, expected weather for the dates, and a smart packing "
            "list tuned to {interests} and the season."
        ),
        backstory=(
            "A former tour operations manager obsessed with smooth logistics. You "
            "think in routes, transfer times, and contingencies, and you pack light "
            "but never forget the one thing that matters."
        ),
        tools=[web, weather, flights, lodging],
        **common,
    )

    curator = Agent(
        role="Local Experience & Food Curator",
        goal=(
            "Surface the experiences in {destination} worth building a trip around "
            "for someone into {interests} — signature sights, food, and a few "
            "lesser-known gems locals would recommend."
        ),
        backstory=(
            "A well-travelled food-and-culture writer with an allergy to tourist "
            "traps. You balance the must-sees with authentic, memorable moments and "
            "always note dietary and accessibility angles when relevant."
        ),
        tools=[web, places],
        **common,
    )

    architect = Agent(
        role="Itinerary Architect",
        goal=(
            "Turn the research, logistics, and experiences into a realistic "
            "day-by-day itinerary for a {duration_days}-day trip at a {pace} pace, "
            "grouped geographically to minimise backtracking."
        ),
        backstory=(
            "A planner who choreographs days like a director: morning, afternoon, "
            "evening, with travel time, meals, rest, and a backup for rain. You "
            "never overstuff a day and you respect the traveler's chosen pace."
        ),
        tools=[web],
        **common,
    )

    budget = Agent(
        role="Budget Analyst",
        goal=(
            "Produce a clear, itemised cost estimate for {travelers} traveler(s) "
            "against the stated budget of {budget}, with money-saving tips and a "
            "realistic total range."
        ),
        backstory=(
            "A numbers-driven travel economist. You give honest ranges (low / "
            "typical / splurge), call out where the money really goes, and flag "
            "when a budget is tight for the plan so expectations stay realistic."
        ),
        tools=[web, currency, flights, lodging],
        **common,
    )

    concierge = Agent(
        role="Travel Concierge & Editor",
        goal=(
            "Assemble everything into one polished, friendly, well-structured "
            "trip plan in Markdown that the traveler can actually use."
        ),
        backstory=(
            "A five-star concierge with an editor's eye. You weave the specialists' "
            "work into a single coherent document — no contradictions, no "
            "duplication — that reads like it was written by one expert host."
        ),
        tools=[],
        **common,
    )

    return {
        "researcher": researcher,
        "logistics": logistics,
        "curator": curator,
        "architect": architect,
        "budget": budget,
        "concierge": concierge,
    }
