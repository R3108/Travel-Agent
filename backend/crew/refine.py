"""Single-agent follow-up editor: revise an existing plan from a user instruction.

The full six-agent crew produces the initial plan; refinement is a lighter,
interactive loop. One concierge/editor agent takes the finished Markdown plus a
natural-language tweak ("make day 2 more relaxed", "add vegetarian options") and
returns a revised plan, preserving everything the user didn't ask to change.
"""

from __future__ import annotations

from crewai import Agent, Crew, Process, Task

from ..models import TripRequest
from .agents import build_llm


def refine_plan(original_markdown: str, instruction: str, req: TripRequest) -> str:
    """Apply a free-form edit to an existing trip plan and return the new Markdown."""
    editor = Agent(
        role="Travel Concierge & Editor",
        goal=(
            "Revise an existing trip plan to satisfy the traveler's request while "
            "keeping everything else intact, coherent, and well-structured."
        ),
        backstory=(
            "A five-star concierge with an editor's eye. You make precise, minimal "
            "edits — honouring the traveler's request without rewriting parts they "
            "were happy with, and never introducing contradictions."
        ),
        llm=build_llm(),
        allow_delegation=False,
        verbose=True,
    )

    task = Task(
        description=(
            "Here is the traveler's current trip plan for "
            f"{req.destination} ({req.duration_days} days, {req.travelers} "
            "traveler(s)):\n\n"
            "-----BEGIN PLAN-----\n"
            f"{original_markdown}\n"
            "-----END PLAN-----\n\n"
            "Apply this requested change, and ONLY this change, keeping the rest of "
            f"the plan as-is:\n\n\"{instruction}\"\n\n"
            "Return the COMPLETE revised plan in clean Markdown — not a diff, not a "
            "summary of what you changed. Keep the same overall structure and "
            "headings. Make sure the result stays internally consistent (e.g. if you "
            "change a day, update the budget or logistics it affects)."
        ),
        expected_output=(
            "The full revised trip plan in Markdown, structurally similar to the "
            "original but reflecting the requested change."
        ),
        agent=editor,
    )

    crew = Crew(
        agents=[editor],
        tasks=[task],
        process=Process.sequential,
        memory=False,
        verbose=True,
    )
    result = crew.kickoff()
    return str(result)
