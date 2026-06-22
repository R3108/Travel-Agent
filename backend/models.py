"""Pydantic request/response models for the planning API."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Pace(str, Enum):
    relaxed = "relaxed"
    balanced = "balanced"
    packed = "packed"


class TripRequest(BaseModel):
    """Everything the crew needs to plan a trip."""

    destination: str = Field(..., min_length=2, examples=["Kyoto, Japan"])
    origin: Optional[str] = Field(None, examples=["London, UK"])
    duration_days: int = Field(..., ge=1, le=60, examples=[5])
    travelers: int = Field(1, ge=1, le=20)
    budget: Optional[str] = Field(
        None,
        description="Free-form budget, e.g. '$2000 total' or 'mid-range'.",
        examples=["$2500 total"],
    )
    start_date: Optional[str] = Field(
        None, description="Optional ISO date or month, e.g. '2026-09-12'."
    )
    interests: list[str] = Field(
        default_factory=list,
        examples=[["food", "temples", "hiking", "photography"]],
    )
    pace: Pace = Pace.balanced
    notes: Optional[str] = Field(
        None, description="Any extra constraints (dietary, accessibility, etc.)."
    )

    @field_validator("interests")
    @classmethod
    def _clean_interests(cls, v: list[str]) -> list[str]:
        return [i.strip() for i in v if i and i.strip()]


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class StageStatus(str, Enum):
    pending = "pending"
    running = "running"
    done = "done"


class Stage(BaseModel):
    """One step in the sequential crew pipeline, for live progress."""

    key: str
    label: str
    status: StageStatus = StageStatus.pending


class PlanJob(BaseModel):
    """Status + result envelope for an async planning job."""

    job_id: str
    status: JobStatus
    request: TripRequest
    progress: list[Stage] = Field(default_factory=list)
    result_markdown: Optional[str] = None
    error: Optional[str] = None
    created_at: float
    updated_at: float


class CreateJobResponse(BaseModel):
    job_id: str
    status: JobStatus


class RefineRequest(BaseModel):
    """A natural-language follow-up edit to an existing plan."""

    instruction: str = Field(
        ...,
        min_length=2,
        max_length=500,
        examples=["Make day 2 more relaxed and add a vegetarian dinner."],
    )


class PlanSummary(BaseModel):
    """Lightweight record for the trip-history list."""

    job_id: str
    status: JobStatus
    destination: str
    duration_days: int
    travelers: int
    created_at: float
