"""Command-line entry point — plan a trip without the web server.

Usage:
    python -m backend.cli "Kyoto, Japan" --days 5 --interests food,temples,hiking
"""

from __future__ import annotations

import argparse

from .config import get_settings
from .crew.trip_crew import plan_trip
from .models import Pace, TripRequest


def main() -> None:
    p = argparse.ArgumentParser(description="Trip Trailers — plan a trip from the CLI.")
    p.add_argument("destination")
    p.add_argument("--origin", default=None)
    p.add_argument("--days", type=int, default=5)
    p.add_argument("--travelers", type=int, default=1)
    p.add_argument("--budget", default=None)
    p.add_argument("--start-date", default=None)
    p.add_argument("--interests", default="", help="comma-separated")
    p.add_argument("--pace", choices=[p.value for p in Pace], default="balanced")
    p.add_argument("--notes", default=None)
    args = p.parse_args()

    if not get_settings().has_llm_key:
        raise SystemExit(
            "No LLM API key is set. Put OPENROUTER_API_KEY (or GEMINI_API_KEY) in .env to match your MODEL."
        )

    req = TripRequest(
        destination=args.destination,
        origin=args.origin,
        duration_days=args.days,
        travelers=args.travelers,
        budget=args.budget,
        start_date=args.start_date,
        interests=[s.strip() for s in args.interests.split(",") if s.strip()],
        pace=Pace(args.pace),
        notes=args.notes,
    )
    print(f"\nPlanning {args.days} days in {args.destination}…\n")
    print(plan_trip(req))


if __name__ == "__main__":
    main()
