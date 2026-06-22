"""Lodging finder (keyless) — real hotels/hostels/guesthouses via OpenStreetMap."""

from __future__ import annotations

from typing import Type

import httpx
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from .geo import USER_AGENT, geocode


class LodgingInput(BaseModel):
    location: str = Field(..., description="City/area to find places to stay in.")
    style: str = Field(
        "any",
        description="One of: any, hotel, hostel, guest_house, apartment.",
    )


_STYLE_TO_OSM = {
    "hotel": ["hotel"],
    "hostel": ["hostel"],
    "guest_house": ["guest_house"],
    "apartment": ["apartment"],
    "any": ["hotel", "hostel", "guest_house", "apartment"],
}


class LodgingTool(BaseTool):
    name: str = "find_lodging"
    description: str = (
        "Find real places to stay (hotels, hostels, guesthouses, apartments) in a "
        "destination via OpenStreetMap — no API key. Returns named lodging to "
        "anchor where to base the trip and to ground accommodation budgeting."
    )
    args_schema: Type[BaseModel] = LodgingInput

    def _run(self, location: str, style: str = "any") -> str:
        try:
            geo = geocode(location)
            if not geo:
                return self._fallback(location, style, note="(location not geocoded)")
            lat, lon, _ = geo
            kinds = _STYLE_TO_OSM.get(style.lower(), _STYLE_TO_OSM["any"])
            regex = "|".join(kinds)
            query = (
                f"[out:json][timeout:25];"
                f'(node["tourism"~"^({regex})$"](around:6000,{lat},{lon});'
                f' way["tourism"~"^({regex})$"](around:6000,{lat},{lon}););'
                f"out center 20;"
            )
            resp = httpx.post(
                "https://overpass-api.de/api/interpreter",
                data={"data": query},
                headers=USER_AGENT,
                timeout=40,
            )
            resp.raise_for_status()
            seen: list[str] = []
            for el in resp.json().get("elements", []):
                tags = el.get("tags", {})
                name = tags.get("name") or tags.get("name:en")
                kind = tags.get("tourism", "")
                if name and name not in seen:
                    seen.append(f"{name} ({kind})")
                if len(seen) >= 15:
                    break
            if not seen:
                return self._fallback(location, style, note="(no named results)")
            listed = "\n".join(f"- {n}" for n in seen)
            return f"Places to stay in {location} (via OpenStreetMap):\n{listed}"
        except Exception as exc:
            return self._fallback(location, style, note=f"(live lookup failed: {exc})")

    def _fallback(self, location: str, style: str, note: str = "") -> str:
        prefix = f"{note}\n" if note else ""
        return (
            f"{prefix}[Live lodging lookup unavailable for {location}.]\n"
            f"Recommend well-known {style} options and good neighbourhoods to stay "
            f"in {location} from your knowledge, with rough nightly price bands."
        )
