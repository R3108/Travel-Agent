# ✦ Trip Trailers

An agentic AI trip planner. Describe a trip and a **crew of six specialist
agents** — research, logistics & weather, experiences & food, itinerary,
budget, and a concierge editor — collaborate to produce a polished, day-by-day
plan.

Built with **CrewAI** for orchestration, **Google Gemini** as the reasoning
engine, a **FastAPI** backend, and a lightweight web UI.

---

## How it works

```
                         ┌──────────────── FastAPI (backend/main.py) ───────────────┐
   Web UI  ──POST /api/plan──▶  async job runner (backend/jobs.py)                   │
  (frontend/)  ◀─poll GET──     │                                                    │
                                ▼                                                    │
                       CrewAI sequential process (backend/crew/trip_crew.py)        │
                                                                                     │
   Research ─▶ Logistics ─▶ Experiences ─▶ Itinerary ─▶ Budget ─▶ Budget-fit ─▶ Concierge ─▶ Plan │
      │            │             │                                                   │
      └─ tools: web_search · weather_lookup · find_places (mock fallback) ──────────┘
```

Each agent runs on Google Gemini (via CrewAI's LiteLLM wrapper, model string
`anthropic/claude-opus-4-8`) and shares a pool of pluggable tools. Tasks run
**sequentially**, each feeding the next, so the itinerary builds on the
research and the final plan reconciles everything.

## Tools & integrations (all optional)

| Tool               | Live source                                  | Key needed? | Fallback                |
| ------------------ | -------------------------------------------- | ----------- | ----------------------- |
| `web_search`       | DuckDuckGo + Wikipedia (Tavily/Serper if set)| **No**      | Model knowledge, flagged |
| `find_places`      | OpenStreetMap (Nominatim/Overpass)           | **No**      | Model knowledge         |
| `find_lodging`     | OpenStreetMap (hotels/hostels/guesthouses)   | **No**      | Model knowledge         |
| `flight_estimate`  | OSM geocoding + great-circle distance/time   | **No**      | Model knowledge         |
| `currency_convert` | ECB rates via Frankfurter.app                | **No**      | Model knowledge         |
| `weather_lookup`   | Open-Meteo (current + 7-day forecast)        | **No**      | Seasonal knowledge      |

**Every tool fetches real-time data with no API key.** Optional keys only
*upgrade* a tool: `OPENWEATHER_API_KEY` swaps weather to OpenWeather, and
`TAVILY_API_KEY`/`SERPER_API_KEY` upgrade web search to premium results. The app
runs end-to-end with **only a Gemini API key** and degrades gracefully if a
network call fails.

## Features

- **Six-agent crew** that researches, plans, budgets, and edits collaboratively.
- **Budget-aligned final itinerary** — after costing the draft, the Itinerary
  Architect revises the day-by-day plan to actually *fit* the budget (swapping
  pricey items for high-value alternatives, or suggesting upgrades when there's
  room) and annotates each day with an estimated cost and a reconciled trip total.
- **Live stage progress** — the UI shows each agent finishing in real time
  (driven by CrewAI task callbacks, not a fake timer), with a live **elapsed timer**.
- **Conversational refinement** — once a plan is ready, ask for a tweak in plain
  English ("make day 2 relaxed, add vegetarian dinners") and a single concierge
  editor agent revises the plan in place (`POST /api/plan/{id}/refine`).
- **Trip history** — completed plans persist to `data/plans/` and reload from a
  "Recent trips" list, with **search/filter** and one-click **re-plan** (loads a
  past trip's settings back into the form to duplicate and tweak).
- **Export** — download any plan as Markdown or a self-contained styled **HTML**
  file, **copy** it to the clipboard, or Print/Save-to-PDF with a clean stylesheet.
- **Interest chips** for fast input, plus pace, budget, and free-form notes.

## Setup

```bash
# 1. Create a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure secrets
copy .env.example .env        # Windows  (cp on macOS/Linux)
#   then edit .env and set GEMINI_API_KEY (https://aistudio.google.com/app/apikey)
```

## Run

**Web app:**

```bash
python -m backend.main
# open http://127.0.0.1:8000
```

**CLI (no browser):**

```bash
python -m backend.cli "Kyoto, Japan" --days 5 --interests food,temples,hiking --budget "$2500"
```

## API

| Method   | Path                          | Purpose                                   |
| -------- | ----------------------------- | ----------------------------------------- |
| `GET`    | `/api/health`                 | Server + integration status               |
| `POST`   | `/api/plan`                   | Start a planning job → `{ job_id }`        |
| `GET`    | `/api/plan/{job_id}`          | Poll job status + live stage progress      |
| `POST`   | `/api/plan/{job_id}/refine`   | Revise a finished plan from an instruction |
| `GET`    | `/api/plan/{job_id}/download` | Download the finished plan as Markdown     |
| `DELETE` | `/api/plan/{job_id}`          | Delete a saved trip                        |
| `GET`    | `/api/plans`                  | List recent trips (history)                |

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/plan \
  -H "Content-Type: application/json" \
  -d '{"destination":"Lisbon, Portugal","duration_days":4,"interests":["food","history"]}'
```

## Project layout

```
Trip-Trailers/
├── backend/
│   ├── main.py            FastAPI app + static hosting
│   ├── jobs.py            async job runner (thread pool + polling)
│   ├── config.py          env-driven settings
│   ├── models.py          request/response schemas
│   ├── cli.py             command-line planner
│   └── crew/
│       ├── trip_crew.py   crew assembly + kickoff
│       ├── refine.py      single-agent follow-up editor (plan refinement)
│       ├── agents.py      the six specialist agents (Gemini)
│       ├── tasks.py       sequential task graph
│       └── tools/         web_search · weather · places
├── frontend/              index.html · styles.css · app.js
├── requirements.txt
└── .env.example
```

## Notes & next steps

- A planning run takes a couple of minutes (six LLM-driven stages). The backend
  runs it off-thread and the UI polls every 3s.
- The job store is in-memory and single-process. For production, swap in a real
  queue (Celery/RQ) + shared store (Redis/Postgres) — the `backend/jobs.py`
  interface is small and easy to replace.
- To enable live search/weather, drop the relevant keys into `.env`.

---

Generated with [Claude Code](https://claude.com/claude-code).
