"""Places / attractions tool.

Uses the free OpenStreetMap Nominatim + Overpass APIs when reachable (no key
required), and falls back to model knowledge otherwise. Kept intentionally
lightweight so the app works offline-ish out of the box.
"""

from __future__ import annotations

from typing import Type

import httpx
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

_UA = {"User-Agent": "TripTrailers/1.0 (trip planner demo)"}


class PlacesInput(BaseModel):
    location: str = Field(..., description="City / area to search around, e.g. 'Kyoto'.")
    category: str = Field(
        "attraction",
        description="One of: attraction, restaurant, museum, park, viewpoint, cafe.",
    )


_CATEGORY_TO_OSM = {
    "attraction": ("tourism", "attraction"),
    "museum": ("tourism", "museum"),
    "viewpoint": ("tourism", "viewpoint"),
    "park": ("leisure", "park"),
    "restaurant": ("amenity", "restaurant"),
    "cafe": ("amenity", "cafe"),
}


class PlacesTool(BaseTool):
    name: str = "find_places"
    description: str = (
        "Find notable places near a destination by category (attraction, "
        "restaurant, museum, park, viewpoint, cafe). Returns named points of "
        "interest to anchor an itinerary. Uses OpenStreetMap (no API key)."
    )
    args_schema: Type[BaseModel] = PlacesInput

    def _run(self, location: str, category: str = "attraction") -> str:
        try:
            return self._osm(location, category)
        except Exception as exc:
            return self._mock(location, category, note=f"(live lookup failed: {exc})")

    def _osm(self, location: str, category: str) -> str:
        key, value = _CATEGORY_TO_OSM.get(category.lower(), ("tourism", "attraction"))
        geo = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": location, "format": "json", "limit": 1},
            headers=_UA,
            timeout=30,
        )
        geo.raise_for_status()
        hits = geo.json()
        if not hits:
            return self._mock(location, category, note="(location not geocoded)")
        lat, lon = hits[0]["lat"], hits[0]["lon"]
        query = (
            f"[out:json][timeout:25];"
            f'(node["{key}"="{value}"](around:8000,{lat},{lon}););'
            f"out body 25;"
        )
        ov = httpx.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": query},
            headers=_UA,
            timeout=40,
        )
        ov.raise_for_status()
        elements = ov.json().get("elements", [])
        names = []
        for el in elements:
            tags = el.get("tags", {})
            name = tags.get("name") or tags.get("name:en")
            if name and name not in names:
                names.append(name)
            if len(names) >= 15:
                break
        if not names:
            return self._mock(location, category, note="(no named results)")
        listed = "\n".join(f"- {n}" for n in names)
        return f"{category.title()}s near {location} (via OpenStreetMap):\n{listed}"

    def _mock(self, location: str, category: str, note: str = "") -> str:
        prefix = f"{note}\n" if note else ""
        return (
            f"{prefix}[Live places lookup unavailable for {category} in {location}.]\n"
            f"Use your own knowledge to recommend well-known and lesser-known "
            f"{category} options in {location}, noting roughly where each sits so "
            "they can be grouped geographically in the itinerary."
        )
