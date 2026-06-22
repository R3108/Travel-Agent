"""Weather tool.

Keyless by default via Open-Meteo (current conditions + multi-day forecast,
no signup). If OPENWEATHER_API_KEY is set, OpenWeather is used instead. Final
fallback is the model's seasonal knowledge.
"""

from __future__ import annotations

from typing import Type

import httpx
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from ...config import get_settings
from .geo import geocode

# Condensed WMO weather-code → description map (Open-Meteo uses WMO codes).
_WMO = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "depositing rime fog",
    51: "light drizzle", 53: "moderate drizzle", 55: "dense drizzle",
    56: "light freezing drizzle", 57: "dense freezing drizzle",
    61: "slight rain", 63: "moderate rain", 65: "heavy rain",
    66: "light freezing rain", 67: "heavy freezing rain",
    71: "slight snow", 73: "moderate snow", 75: "heavy snow", 77: "snow grains",
    80: "slight rain showers", 81: "moderate rain showers", 82: "violent rain showers",
    85: "slight snow showers", 86: "heavy snow showers",
    95: "thunderstorm", 96: "thunderstorm with slight hail", 99: "thunderstorm with heavy hail",
}


class WeatherInput(BaseModel):
    location: str = Field(..., description="City / place name, e.g. 'Kyoto, Japan'.")


class WeatherTool(BaseTool):
    name: str = "weather_lookup"
    description: str = (
        "Look up current weather plus a multi-day forecast for a destination, to "
        "inform timing, daily planning, and a packing list. Works with no API key "
        "(Open-Meteo). Input is a place name."
    )
    args_schema: Type[BaseModel] = WeatherInput

    def _run(self, location: str) -> str:
        settings = get_settings()
        # Premium provider first if configured.
        if settings.openweather_api_key:
            try:
                return self._openweather(location, settings.openweather_api_key)
            except Exception:
                pass  # fall through to keyless
        # Keyless default.
        try:
            out = self._open_meteo(location)
            if out:
                return out
        except Exception as exc:
            return self._knowledge_fallback(location, note=f"(live weather failed: {exc})")
        return self._knowledge_fallback(location)

    # --- Keyless: Open-Meteo ---
    def _open_meteo(self, location: str) -> str:
        geo = geocode(location)
        if not geo:
            return self._knowledge_fallback(location, note="(location not geocoded)")
        lat, lon, name = geo
        resp = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,apparent_temperature,relative_humidity_2m,"
                           "weather_code,wind_speed_10m",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                         "precipitation_probability_max",
                "timezone": "auto",
                "forecast_days": 7,
            },
            timeout=25,
        )
        resp.raise_for_status()
        data = resp.json()
        cur = data.get("current", {})
        units = data.get("current_units", {})
        temp_u = units.get("temperature_2m", "°C")

        desc = _WMO.get(cur.get("weather_code"), "unknown conditions")
        lines = [
            f"Weather for {name} (live, Open-Meteo):",
            f"- Now: {desc}, {cur.get('temperature_2m')}{temp_u} "
            f"(feels {cur.get('apparent_temperature')}{temp_u}), "
            f"humidity {cur.get('relative_humidity_2m')}%, "
            f"wind {cur.get('wind_speed_10m')} {units.get('wind_speed_10m', 'km/h')}",
        ]

        daily = data.get("daily", {})
        days = daily.get("time", []) or []
        if days:
            lines.append("- Next days:")
            for i, day in enumerate(days[:7]):
                d_desc = _WMO.get(daily["weather_code"][i], "—")
                hi = daily["temperature_2m_max"][i]
                lo = daily["temperature_2m_min"][i]
                pop = daily["precipitation_probability_max"][i]
                lines.append(f"    {day}: {lo}-{hi}{temp_u}, {d_desc}, precip {pop}%")
        lines.append(
            "Note: the forecast covers the next ~7 days. For travel dates further "
            "out, combine this with typical seasonal patterns and build the packing "
            "list accordingly."
        )
        return "\n".join(lines)

    # --- Premium: OpenWeather ---
    def _openweather(self, location: str, key: str) -> str:
        g = httpx.get(
            "https://api.openweathermap.org/geo/1.0/direct",
            params={"q": location, "limit": 1, "appid": key},
            timeout=30,
        )
        g.raise_for_status()
        places = g.json()
        if not places:
            return self._knowledge_fallback(location, note="(location not found)")
        lat, lon = places[0]["lat"], places[0]["lon"]
        w = httpx.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"lat": lat, "lon": lon, "appid": key, "units": "metric"},
            timeout=30,
        )
        w.raise_for_status()
        d = w.json()
        return (
            f"Current weather in {location} (OpenWeather): "
            f"{d['weather'][0]['description']}, {d['main']['temp']}°C "
            f"(feels {d['main']['feels_like']}°C), humidity {d['main']['humidity']}%. "
            "Combine with seasonal patterns for the travel dates and build a packing list."
        )

    # --- Fallback ---
    def _knowledge_fallback(self, location: str, note: str = "") -> str:
        prefix = f"{note}\n" if note else ""
        return (
            f"{prefix}[Live weather unavailable for {location}.]\n"
            "Use your knowledge of the destination's climate and seasonal patterns "
            "for the requested dates (temperature range, rain likelihood, daylight) "
            "and produce a packing list. Suggest checking a live forecast a few days "
            "before departure."
        )
