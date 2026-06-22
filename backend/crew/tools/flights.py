"""Flight / travel estimate tool (keyless).

There is no reliable keyless live-fare API, so this tool grounds the budget and
logistics agents with *real* facts — geocoded great-circle distance and a
derived flight duration — plus a clearly-labelled rough fare band. The agents
are told to refine the fare with web_search.
"""

from __future__ import annotations

from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from .geo import geocode, haversine_km


class FlightInput(BaseModel):
    origin: str = Field(..., description="Departure city/airport, e.g. 'London, UK'.")
    destination: str = Field(..., description="Arrival city, e.g. 'Kyoto, Japan'.")


class FlightEstimateTool(BaseTool):
    name: str = "flight_estimate"
    description: str = (
        "Estimate travel between two places: real great-circle distance and "
        "approximate flight duration (keyless geocoding), plus a rough fare band. "
        "Use it to ground transport planning and budgets, then refine fares with "
        "web_search."
    )
    args_schema: Type[BaseModel] = FlightInput

    def _run(self, origin: str, destination: str) -> str:
        try:
            a = geocode(origin)
            b = geocode(destination)
        except Exception as exc:
            return f"[Could not geocode route ({exc}); estimate distance from knowledge.]"
        if not a or not b:
            return (
                f"[Could not geocode '{origin}' or '{destination}'. Estimate the "
                "distance, flight time, and fare from your own knowledge.]"
            )

        dist = haversine_km(a[0], a[1], b[0], b[1])

        if dist < 300:
            return (
                f"{origin} -> {destination}: ~{dist:.0f} km apart. This is short — "
                "ground transport (train/bus/car) is likely better than flying. "
                "Use web_search for train/bus options and fares."
            )

        # Flight time: cruise ~800 km/h + ~1.5h for taxi/climb/descent/buffer.
        hours = dist / 800 + 1.5
        # Rough one-way economy fare band (heuristic, USD) — clearly an estimate.
        low = max(40, dist * 0.07)
        typical = max(60, dist * 0.11)
        high = max(90, dist * 0.18)
        return (
            f"{origin} -> {destination}\n"
            f"- Distance: ~{dist:.0f} km (great-circle, real geocoded value)\n"
            f"- Est. flight time: ~{hours:.1f} h non-stop (longer with layovers)\n"
            f"- ROUGH one-way economy fare band (estimate only): "
            f"${low:.0f} (deal) / ${typical:.0f} (typical) / ${high:.0f} (peak)\n"
            "Treat the fare band as a heuristic — confirm real prices with "
            "web_search for the actual travel dates."
        )
