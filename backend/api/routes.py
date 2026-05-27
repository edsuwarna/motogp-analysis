"""
MotoGP Analysis — FastAPI routes for events, sessions, standings, teams.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core.database import get_session
from backend.models.models import (
    Event, Session as MotoSession, Result, RiderStanding,
    ConstructorStanding, Team, Category, Season
)

router = APIRouter()


# ── Seasons ──

@router.get("/seasons")
async def get_seasons(db: AsyncSession = Depends(get_session)):
    res = await db.execute(
        select(Season).order_by(Season.year.desc()).limit(5)
    )
    return [{"year": s.year, "current": s.current} for s in res.scalars()]


# ── Categories ──

@router.get("/categories")
async def get_categories(
    year: int = Query(2026),
    db: AsyncSession = Depends(get_session),
):
    res = await db.execute(
        select(Category).where(Category.season_year == year)
    )
    return [
        {"id": c.id, "name": c.name.replace("™", ""), "legacy_id": c.legacy_id}
        for c in res.scalars()
    ]


# ── Events ──

@router.get("/events")
async def get_events(
    year: int = Query(2026),
    db: AsyncSession = Depends(get_session),
):
    res = await db.execute(
        select(Event)
        .where(Event.season_year == year)
        .order_by(Event.round)
    )
    events = []
    for e in res.scalars():
        # Count sessions per event
        s_res = await db.execute(
            select(func.count(MotoSession.id)).where(MotoSession.event_id == e.id)
        )
        session_count = s_res.scalar() or 0
        events.append({
            "id": e.id,
            "round": e.round,
            "name": e.name,
            "short_name": e.short_name,
            "circuit_name": e.circuit_name,
            "country": e.country,
            "country_iso": e.country_iso,
            "date_start": e.date_start,
            "date_end": e.date_end,
            "sponsored_name": e.sponsored_name,
            "session_count": session_count,
            "status": e.status,
        })
    return events


@router.get("/events/{event_id}")
async def get_event(
    event_id: str,
    db: AsyncSession = Depends(get_session),
):
    res = await db.execute(select(Event).where(Event.id == event_id))
    e = res.scalar_one_or_none()
    if not e:
        return {"error": "Event not found"}
    return {
        "id": e.id,
        "round": e.round,
        "name": e.name,
        "short_name": e.short_name,
        "circuit_name": e.circuit_name,
        "country": e.country,
        "country_iso": e.country_iso,
        "date_start": e.date_start,
        "date_end": e.date_end,
        "sponsored_name": e.sponsored_name,
        "status": e.status,
    }


@router.get("/events/{event_id}/sessions")
async def get_event_sessions(
    event_id: str,
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_session),
):
    q = select(MotoSession).where(MotoSession.event_id == event_id)
    if category:
        q = q.where(MotoSession.category_id == category)
    q = q.order_by(MotoSession.number)

    res = await db.execute(q)
    sessions = []
    for s in res.scalars():
        sessions.append({
            "id": s.id,
            "type": s.type,
            "number": s.number,
            "category_id": s.category_id,
            "date": s.date,
            "status": s.status,
            "track_condition": s.track_condition,
            "air_temp": s.air_temp,
            "ground_temp": s.ground_temp,
            "humidity": s.humidity,
            "weather": s.weather,
        })
    return sessions


# ── Session Results ──

@router.get("/sessions/{session_id}")
async def get_session_detail(
    session_id: str,
    db: AsyncSession = Depends(get_session),
):
    res = await db.execute(select(MotoSession).where(MotoSession.id == session_id))
    s = res.scalar_one_or_none()
    if not s:
        return {"error": "Session not found"}
    return {
        "id": s.id,
        "event_id": s.event_id,
        "category_id": s.category_id,
        "type": s.type,
        "number": s.number,
        "date": s.date,
        "status": s.status,
        "track_condition": s.track_condition,
        "air_temp": s.air_temp,
        "ground_temp": s.ground_temp,
        "humidity": s.humidity,
        "weather": s.weather,
    }


@router.get("/sessions/{session_id}/results")
async def get_session_results(
    session_id: str,
    db: AsyncSession = Depends(get_session),
):
    res = await db.execute(
        select(Result).where(Result.session_id == session_id)
        .order_by(Result.position.nulls_last())
    )
    results = []
    for r in res.scalars():
        results.append({
            "position": r.position,
            "rider_id": r.rider_id,
            "rider_name": r.rider_name,
            "rider_number": r.rider_number,
            "rider_country": r.rider_country,
            "team_name": r.team_name,
            "constructor_name": r.constructor_name,
            "total_time": r.total_time,
            "gap_first": r.gap_first,
            "gap_prev": r.gap_prev,
            "best_lap_time": r.best_lap_time,
            "best_lap_number": r.best_lap_number,
            "total_laps": r.total_laps,
            "top_speed": r.top_speed,
            "status": r.status,
        })
    return results


# ── Standings ──

@router.get("/standings/riders")
async def get_rider_standings(
    year: int = Query(2026),
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_session),
):
    q = select(RiderStanding).where(RiderStanding.season_year == year)
    if category:
        q = q.where(RiderStanding.category_id == category)
    q = q.order_by(RiderStanding.position)

    res = await db.execute(q)
    standings = []
    for s in res.scalars():
        standings.append({
            "position": s.position,
            "rider_id": s.rider_id,
            "rider_name": s.rider_name,
            "rider_number": s.rider_number,
            "rider_country": s.rider_country,
            "team_name": s.team_name,
            "constructor_name": s.constructor_name,
            "points": s.points,
        })
    return standings


@router.get("/standings/constructors")
async def get_constructor_standings(
    year: int = Query(2026),
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_session),
):
    q = select(ConstructorStanding).where(ConstructorStanding.season_year == year)
    if category:
        q = q.where(ConstructorStanding.category_id == category)
    q = q.order_by(ConstructorStanding.position)

    res = await db.execute(q)
    standings = []
    for s in res.scalars():
        standings.append({
            "position": s.position,
            "constructor_name": s.constructor_name,
            "points": s.points,
        })
    return standings


# ── Teams ──

@router.get("/teams")
async def get_teams(
    year: int = Query(2026),
    db: AsyncSession = Depends(get_session),
):
    res = await db.execute(
        select(Team).where(Team.season_year == year)
        .order_by(Team.name)
    )
    teams = []
    for t in res.scalars():
        teams.append({
            "id": t.id,
            "name": t.name,
            "constructor_name": t.constructor_name,
            "color": t.color,
            "text_color": t.text_color,
            "picture": t.picture,
        })
    return teams


# ── Dashboard Summary ──

@router.get("/dashboard")
async def get_dashboard(
    year: int = Query(2026),
    db: AsyncSession = Depends(get_session),
):
    """Return summary stats for the dashboard hero."""
    ev_res = await db.execute(
        select(func.count(Event.id)).where(Event.season_year == year)
    )
    total_gp = ev_res.scalar() or 0

    rd_res = await db.execute(
        select(RiderStanding).where(
            RiderStanding.season_year == year,
            RiderStanding.position <= 3,
        ).order_by(RiderStanding.position)
    )
    top3 = rd_res.scalars().all()

    sr_res = await db.execute(
        select(func.count(Result.id))
    )
    total_results = sr_res.scalar() or 0

    return {
        "year": year,
        "total_events": total_gp,
        "total_results": total_results,
        "top_3": [
            {
                "position": r.position,
                "rider_name": r.rider_name,
                "points": r.points,
                "constructor_name": r.constructor_name,
            }
            for r in top3
        ],
    }
