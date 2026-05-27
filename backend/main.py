"""
MotoGP Analysis — FastAPI Backend.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.database import init_db
from backend.api import routes, news


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="MotoGP Analysis API",
    description="MotoGP race results, session data, and standings API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ──
@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Register routes ──
app.include_router(routes.router, prefix="/api", tags=["Data"])
app.include_router(news.router, prefix="/api", tags=["News"])


# ── Serve frontend (optional — CF Pages serves it separately) ──
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
