"""Shared keyless geo helpers (OpenStreetMap Nominatim + haversine)."""

from __future__ import annotations

import math
from typing import Optional

import httpx

USER_AGENT = {"User-Agent": "TripTrailers/1.0 (trip planner demo)"}


def geocode(query: str) -> Optional[tuple[float, float, str]]:
    """Return (lat, lon, display_name) for a place, or None if not found."""
    r = httpx.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": query, "format": "json", "limit": 1},
        headers=USER_AGENT,
        timeout=30,
    )
    r.raise_for_status()
    hits = r.json()
    if not hits:
        return None
    h = hits[0]
    return float(h["lat"]), float(h["lon"]), h.get("display_name", query)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points, in kilometres."""
    radius = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    )
    return radius * 2 * math.asin(math.sqrt(a))
