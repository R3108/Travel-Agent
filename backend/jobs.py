"""In-memory async job runner with live stage progress + disk persistence.

A planning run invokes the whole crew and can take a few minutes, so we run it
off the request thread in a ThreadPoolExecutor and let clients poll for status.
Completed/failed jobs are persisted to ``data/plans/<job_id>.json`` so trip
history survives restarts.

For a single-process demo this is plenty; swap for a real queue (Celery/RQ) and
a shared store (Redis/DB) to scale out.
"""

from __future__ import annotations

import json
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock

from .crew.refine import refine_plan
from .crew.trip_crew import STAGES, plan_trip
from .models import JobStatus, PlanJob, PlanSummary, Stage, StageStatus, TripRequest

_executor = ThreadPoolExecutor(max_workers=3)
_jobs: dict[str, PlanJob] = {}
_lock = Lock()

_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "plans"
_DATA_DIR.mkdir(parents=True, exist_ok=True)


def _now() -> float:
    return time.time()


def _initial_stages() -> list[Stage]:
    return [Stage(key=key, label=label) for key, label in STAGES]


# --------------------------------------------------------------------------- #
# Job lifecycle
# --------------------------------------------------------------------------- #
def create_job(req: TripRequest) -> PlanJob:
    job_id = uuid.uuid4().hex[:12]
    job = PlanJob(
        job_id=job_id,
        status=JobStatus.queued,
        request=req,
        progress=_initial_stages(),
        created_at=_now(),
        updated_at=_now(),
    )
    with _lock:
        _jobs[job_id] = job
    _executor.submit(_run, job_id)
    return job


def get_job(job_id: str) -> PlanJob | None:
    with _lock:
        job = _jobs.get(job_id)
    if job:
        return job
    return _load_from_disk(job_id)


def _update(job_id: str, **fields) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        for k, v in fields.items():
            setattr(job, k, v)
        job.updated_at = _now()


def _advance_stage(job_id: str) -> None:
    """Mark the running stage done and start the next one.

    Called by CrewAI's task_callback after each task completes.
    """
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        for i, stage in enumerate(job.progress):
            if stage.status == StageStatus.running:
                stage.status = StageStatus.done
                if i + 1 < len(job.progress):
                    job.progress[i + 1].status = StageStatus.running
                break
        job.updated_at = _now()


def _start_first_stage(job_id: str) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if job and job.progress:
            job.progress[0].status = StageStatus.running
            job.updated_at = _now()


def _run(job_id: str) -> None:
    with _lock:
        job = _jobs.get(job_id)
    if not job:
        return
    _update(job_id, status=JobStatus.running)
    _start_first_stage(job_id)
    try:
        markdown = plan_trip(
            job.request,
            on_task_complete=lambda: _advance_stage(job_id),
        )
        _update(job_id, status=JobStatus.completed, result_markdown=markdown)
    except Exception as exc:  # surface the failure to the client
        _update(job_id, status=JobStatus.failed, error=f"{type(exc).__name__}: {exc}")
        traceback.print_exc()
    finally:
        saved = get_job(job_id)
        if saved:
            _save_to_disk(saved)


def refine_job(job_id: str, instruction: str) -> PlanJob | None:
    """Apply a follow-up edit to a completed job's plan and persist the result.

    Runs synchronously (a single editor agent); FastAPI offloads the calling
    endpoint to a worker thread so the event loop stays free.
    """
    job = get_job(job_id)
    if not job or job.status != JobStatus.completed or not job.result_markdown:
        return None
    revised = refine_plan(job.result_markdown, instruction, job.request)
    job.result_markdown = revised
    job.updated_at = _now()
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].result_markdown = revised
            _jobs[job_id].updated_at = job.updated_at
    _save_to_disk(job)
    return job


# --------------------------------------------------------------------------- #
# Persistence (trip history)
# --------------------------------------------------------------------------- #
def _path(job_id: str) -> Path:
    return _DATA_DIR / f"{job_id}.json"


def _save_to_disk(job: PlanJob) -> None:
    try:
        _path(job.job_id).write_text(job.model_dump_json(indent=2), encoding="utf-8")
    except Exception:
        traceback.print_exc()


def _load_from_disk(job_id: str) -> PlanJob | None:
    p = _path(job_id)
    if not p.exists():
        return None
    try:
        return PlanJob.model_validate_json(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def list_summaries(limit: int = 50) -> list[PlanSummary]:
    """Return recent trips (in-memory + persisted), newest first."""
    seen: dict[str, PlanJob] = {}
    with _lock:
        for job in _jobs.values():
            seen[job.job_id] = job
    for p in _DATA_DIR.glob("*.json"):
        if p.stem not in seen:
            job = _load_from_disk(p.stem)
            if job:
                seen[job.job_id] = job

    summaries = [
        PlanSummary(
            job_id=j.job_id,
            status=j.status,
            destination=j.request.destination,
            duration_days=j.request.duration_days,
            travelers=j.request.travelers,
            created_at=j.created_at,
        )
        for j in seen.values()
    ]
    summaries.sort(key=lambda s: s.created_at, reverse=True)
    return summaries[:limit]


def delete_job(job_id: str) -> bool:
    removed = False
    with _lock:
        if job_id in _jobs:
            del _jobs[job_id]
            removed = True
    p = _path(job_id)
    if p.exists():
        p.unlink()
        removed = True
    return removed
