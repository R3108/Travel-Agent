"""FastAPI application: planning API + static web frontend."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .jobs import create_job, delete_job, get_job, list_summaries, refine_job
from .models import (
    CreateJobResponse,
    PlanJob,
    PlanSummary,
    RefineRequest,
    TripRequest,
)

app = FastAPI(
    title="Trip Trailers API",
    description="Agentic AI trip planner powered by CrewAI + Google Gemini.",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@app.get("/api/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "model": settings.model,
        "llm_key_configured": settings.has_llm_key,
        "tools": {
            "web_search": "keyless (DuckDuckGo + Wikipedia)"
            + (" + premium" if (settings.tavily_api_key or settings.serper_api_key) else ""),
            "find_places": "keyless (OpenStreetMap)",
            "find_lodging": "keyless (OpenStreetMap)",
            "flight_estimate": "keyless (geocoding)",
            "currency_convert": "keyless (ECB / Frankfurter)",
            "weather_lookup": "premium (OpenWeather)" if settings.openweather_api_key
            else "keyless (Open-Meteo)",
        },
    }


@app.post("/api/plan", response_model=CreateJobResponse)
def create_plan(req: TripRequest) -> CreateJobResponse:
    settings = get_settings()
    if not settings.has_llm_key:
        raise HTTPException(
            status_code=400,
            detail="No LLM API key is configured on the server (set OPENROUTER_API_KEY or GEMINI_API_KEY for the chosen MODEL).",
        )
    job = create_job(req)
    return CreateJobResponse(job_id=job.job_id, status=job.status)


@app.get("/api/plans", response_model=list[PlanSummary])
def list_plans() -> list[PlanSummary]:
    return list_summaries()


@app.get("/api/plan/{job_id}", response_model=PlanJob)
def read_plan(job_id: str) -> PlanJob:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@app.get("/api/plan/{job_id}/download")
def download_plan(job_id: str) -> Response:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if not job.result_markdown:
        raise HTTPException(status_code=409, detail="Plan is not ready yet.")
    slug = re.sub(r"[^a-z0-9]+", "-", job.request.destination.lower()).strip("-") or "trip"
    filename = f"trip-trailers-{slug}.md"
    return Response(
        content=job.result_markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/plan/{job_id}/refine", response_model=PlanJob)
def refine_plan_endpoint(job_id: str, req: RefineRequest) -> PlanJob:
    settings = get_settings()
    if not settings.has_llm_key:
        raise HTTPException(
            status_code=400,
            detail="No LLM API key is configured on the server (set OPENROUTER_API_KEY or GEMINI_API_KEY for the chosen MODEL).",
        )
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.status != "completed" or not job.result_markdown:
        raise HTTPException(
            status_code=409, detail="Only a completed plan can be refined."
        )
    updated = refine_job(job_id, req.instruction.strip())
    if not updated:
        raise HTTPException(status_code=500, detail="Refinement failed.")
    return updated


@app.delete("/api/plan/{job_id}")
def remove_plan(job_id: str) -> dict:
    if not delete_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found.")
    return {"deleted": job_id}


# --- Static frontend (mounted last so /api/* wins) ---
if _FRONTEND_DIR.exists():
    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(_FRONTEND_DIR / "index.html")

    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR)), name="frontend")


def run() -> None:
    """Entry point for `python -m backend.main`."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    run()
