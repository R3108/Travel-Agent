"""Assembles and runs the Trip Trailers crew."""

from __future__ import annotations

from typing import Callable, Optional

from crewai import Crew, Process

from ..models import TripRequest
from .agents import build_agents
from .tasks import build_tasks

# Ordered stages, aligned 1:1 with the tasks in tasks.build_tasks().
# Shared with the job runner so progress labels stay in sync.
STAGES: list[tuple[str, str]] = [
    ("research", "Researching destination"),
    ("logistics", "Logistics & weather"),
    ("experiences", "Experiences & food"),
    ("itinerary", "Building itinerary"),
    ("budget", "Budgeting"),
    ("budget_fit", "Tailoring itinerary to budget"),
    ("compile", "Final concierge edit"),
]


def _to_inputs(req: TripRequest) -> dict:
    """Flatten a TripRequest into the {placeholder} dict the tasks expect."""
    return {
        "destination": req.destination,
        "origin": req.origin or "an unspecified origin",
        "duration_days": req.duration_days,
        "travelers": req.travelers,
        "budget": req.budget or "an unspecified / flexible budget",
        "start_date": req.start_date or "flexible dates",
        "interests": ", ".join(req.interests) if req.interests else "general sightseeing",
        "pace": req.pace.value,
        "notes": req.notes or "none",
    }


def build_crew(on_task_complete: Optional[Callable[[], None]] = None) -> Crew:
    agents = build_agents()
    tasks = build_tasks(agents)
    task_callback = (lambda _output: on_task_complete()) if on_task_complete else None
    return Crew(
        agents=list(agents.values()),
        tasks=tasks,
        process=Process.sequential,
        memory=False,   # avoids requiring an embeddings provider
        verbose=True,
        task_callback=task_callback,
    )


def plan_trip(
    req: TripRequest,
    on_task_complete: Optional[Callable[[], None]] = None,
) -> str:
    """Run the full crew for one trip request and return the final Markdown plan.

    ``on_task_complete`` (if given) is invoked after each task finishes, so the
    caller can advance a live progress indicator.
    """
    crew = build_crew(on_task_complete=on_task_complete)
    result = crew.kickoff(inputs=_to_inputs(req))
    return str(result)
