# 🏍️ MotoGP Analysis 2026

Live standings, race results, and analysis for the 2026 MotoGP World Championship.

**Live site:** [motogp-analysis.edsuwarna.id](https://motogp-analysis.edsuwarna.id)  
**API:** [motogp-api.edsuwarna.id](https://motogp-api.edsuwarna.id)

## Features

- 📊 **Dashboard** — championship top 3 podium, standings bar chart, recent results
- 🏆 **Standings** — rider & constructor standings with category filtering + race-by-race points breakdown
- 🏁 **Races** — complete calendar with Sprint & Race results (positions, gaps, best laps, top speed, weather)
- 📈 **Progression** — cumulative points chart per rider across all rounds + teammate battle comparison
- 🏢 **Teams** — team overview with rider lineups and constructor standings
- 📈 **Season Stats** — wins, podiums, fastest laps, top speeds, rider comparison & form tracker
- 📰 **News** — latest MotoGP news feed
- 🌙 **Dark/Light theme**

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | [FastAPI](https://fastapi.tiangolo.com/) (Python) |
| Database | [SQLite](https://www.sqlite.org/) + aiosqlite + SQLAlchemy async |
| Frontend | Vanilla JS + [TailwindCSS](https://tailwindcss.com/) + [Chart.js](https://www.chartjs.org/) (SPA) |
| Deployment | Backend on VPS · Frontend on [Cloudflare Pages](https://pages.cloudflare.com/) |
| Data Source | [MotoGP pulselive API](https://api.motogp.pulselive.com/motogp/v1) |

## Project Structure

```
motogp-analysis/
├── backend/
│   ├── main.py                 # FastAPI app entry point
│   ├── api/
│   │   ├── routes.py           # Core data endpoints (events, standings, teams)
│   │   ├── analytics.py        # Analytics endpoints (season stats, rider comparison)
│   │   └── news.py             # News scraping endpoint
│   ├── core/
│   │   └── database.py         # SQLAlchemy async setup
│   ├── ingestion/
│   │   ├── ingest_motogp.py    # Main data ingestion pipeline
│   │   └── cli.py              # CLI runner
│   └── models/
│       └── models.py           # SQLAlchemy ORM models
├── frontend/
│   └── index.html              # Single-page application (SPA)
├── Dockerfile                  # Container image
├── docker-compose.yml          # Docker Compose setup
├── .dockerignore
├── requirements.txt
├── LICENSE                     # MIT
└── README.md
```

## Setup (Local Development)

### Prerequisites

- Python 3.11+
- pip

### 1. Clone & Install

```bash
git clone https://github.com/edsuwarna/motogp-analysis.git
cd motogp-analysis
pip install -r requirements.txt
```

### 2. Ingest Data

Populate the SQLite database from the MotoGP pulselive API:

```bash
python -m backend.ingestion.cli
```

This fetches seasons, categories, events, sessions, results, and teams — then computes rider & constructor standings.

> **Note:** `motogp.db` is not included in the repository (gitignored). You must run the ingestion to create it.

### 3. Run Backend

```bash
uvicorn backend.main:app --reload --port 8001
```

### 4. Open Frontend

For development, serve the `frontend/` directory or open `frontend/index.html` with the API pointed to your local backend.

## Docker Setup

### Prerequisites

- Docker & Docker Compose

### 1. Build & Run

```bash
docker compose up -d
```

The API will be available at `http://localhost:8001`. The frontend SPA is served directly by the backend, so all features work out of the box.

### 2. Ingest Data (first run)

```bash
docker compose run --rm api python -m backend.ingestion.cli
```

The SQLite database is stored in a persistent Docker volume (`motogp_data`), so data survives container restarts.

### 3. Stop

```bash
docker compose down
```

### Data Management

| Command | Description |
|---------|-------------|
| `docker compose logs -f` | Follow logs |
| `docker compose restart` | Restart API only |
| `docker compose down -v` | **⚠️ Deletes database volume** |

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/seasons` | List seasons |
| `GET /api/categories?year=2026` | List categories (MotoGP/Moto2/Moto3) |
| `GET /api/events?year=2026` | Race calendar |
| `GET /api/events/{id}/sessions` | Sessions for an event |
| `GET /api/sessions/{id}/results` | Results for a session |
| `GET /api/standings/riders?year=2026` | Rider standings |
| `GET /api/standings/constructors?year=2026` | Constructor standings |
| `GET /api/teams?year=2026` | Team list with colors |
| `GET /api/teams/detail?year=2026` | Teams with riders & points |
| `GET /api/dashboard?year=2026` | Summary stats |
| `GET /api/season/stats?year=2026` | Season statistics |
| `GET /api/sessions/{id}/export/csv` | Export results as CSV |

## License

MIT — see [LICENSE](LICENSE).

## Disclaimer

Data sourced from the official MotoGP pulselive API. Not affiliated with MotoGP or Dorna Sports.
