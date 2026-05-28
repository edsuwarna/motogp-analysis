"""MotoGP Analysis — Analytics API: rider progress, race breakdown, session insights."""

import csv
import io
from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response as FastResponse
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_session
from backend.models.models import (
    Event, Session as MotoSession, Result, RiderStanding,
    ConstructorStanding, Team, Category
)

router = APIRouter()

# ── Points systems ──
RACE_POINTS = {1: 25, 2: 20, 3: 16, 4: 13, 5: 11, 6: 10, 7: 9, 8: 8, 9: 7,
               10: 6, 11: 5, 12: 4, 13: 3, 14: 2, 15: 1}
SPRINT_POINTS = {1: 12, 2: 9, 3: 7, 4: 6, 5: 5, 6: 4, 7: 3, 8: 2, 9: 1}

COUNTRY_FLAGS = {
    "ES": "🇪🇸", "IT": "🇮🇹", "GB": "🇬🇧", "FR": "🇫🇷", "DE": "🇩🇪",
    "NL": "🇳🇱", "AU": "🇦🇺", "JP": "🇯🇵", "ZA": "🇿🇦", "US": "🇺🇸",
    "BR": "🇧🇷", "AR": "🇦🇷", "PT": "🇵🇹", "CH": "🇨🇭", "AT": "🇦🇹",
    "BE": "🇧🇪", "DK": "🇩🇰", "SE": "🇸🇪", "NO": "🇳🇴", "FI": "🇫🇮",
    "IE": "🇮🇪", "PL": "🇵🇱", "CZ": "🇨🇿", "HU": "🇭🇺", "GR": "🇬🇷",
    "TR": "🇹🇷", "TH": "🇹🇭", "MY": "🇲🇾", "ID": "🇮🇩", "IN": "🇮🇳",
    "CN": "🇨🇳", "KR": "🇰🇷", "SG": "🇸🇬", "PH": "🇵🇭", "VN": "🇻🇳",
    "AE": "🇦🇪", "SA": "🇸🇦", "QA": "🇶🇦", "IL": "🇮🇱", "EG": "🇪🇬",
    "MA": "🇲🇦", "NZ": "🇳🇿", "RU": "🇷🇺", "UA": "🇺🇦", "RS": "🇷🇸",
    "SI": "🇸🇮", "SK": "🇸🇰", "HR": "🇭🇷", "LT": "🇱🇹", "LV": "🇱🇻",
    "EE": "🇪🇪", "IS": "🇮🇸", "LU": "🇱🇺", "MT": "🇲🇹", "MC": "🇲🇨",
    "SM": "🇸🇲", "VA": "🇻🇦",
}

# ── Constructor colours ──
CONSTRUCTOR_COLORS = {
    "Aprilia": "#d52b2b",
    "Ducati": "#cc0000",
    "Yamaha": "#0055a5",
    "Honda": "#a5a5a5",
    "KTM": "#ff6600",
    "Kalex": "#0055a5",
    "Boscoscuro": "#8b0000",
    "Forward": "#00a86b",
    "MV Agusta": "#8b4513",
}

# ── Per-team colours (overrides constructor colours for known teams) ──
TEAM_COLORS = {
    # MotoGP
    "Ducati Lenovo Team": "#cc0000",
    "Aprilia Racing": "#9d2235",
    "Honda HRC Castrol": "#a5a5a5",
    "Monster Energy Yamaha MotoGP Team": "#003366",
    "Red Bull KTM Factory Racing": "#ff6600",
    "Red Bull KTM Tech3": "#e85200",
    "BK8 Gresini Racing MotoGP": "#00bfff",
    "Pertamina Enduro VR46 Racing Team": "#e5b80b",
    "Prima Pramac Yamaha MotoGP": "#0055a5",
    "Castrol Honda LCR": "#c02e2e",
    "Trackhouse MotoGP Team": "#1a1a2e",
    "Pro Honda LCR": "#c02e2e",
    # Moto2
    "CFMOTO Gaviota Aspar Team": "#8b0000",
    "CFMOTO Inde Aspar Team": "#8b0000",
    "CFMOTO Impulse Aspar Team": "#8b0000",
    "CFMOTO Power Electronics Aspar Team": "#8b0000",
    "CFMOTO Valresa Aspar Team": "#8b0000",
    "Red Bull KTM Ajo": "#ff6600",
    "ELF Marc VDS Racing Team": "#0066cc",
    "LIQUI MOLY Dynavolt Intact GP": "#004d99",
    "Liqui Moly Dynavolt Intact GP": "#004d99",
    "ITALJET Gresini Moto2": "#00bfff",
    "Idemitsu Honda Team Asia": "#a5a5a5",
    "Italtrans Racing Team": "#1a1a2e",
    "OnlyFans American Racing Team": "#cc0000",
    "QJMOTOR - Bordoy - MSI": "#003366",
    "QJMOTOR - El Motorista - MSI": "#003366",
    "QJMOTOR - GALFER - MSI": "#003366",
    "QJMOTOR - PONT GRUP - MSI": "#003366",
    "AEON Credit - MT Helmets - MSI": "#003366",
    "Beta Tools SpeedRS Team": "#8b0000",
    "BLU CRU Pramac Yamaha Moto2": "#0055a5",
    "Folladore SpeedRS Team": "#8b0000",
    "HDR SpeedRS Team": "#8b0000",
    "SYNC Group SpeedRS Team": "#8b0000",
    "Momoven Idrofoglia RW Racing Team": "#2e8b57",
    "GRYD - MLav Racing": "#a5a5a5",
    "Klint Forward Team": "#00a86b",
    "KLINT Racing Team": "#00a86b",
    "Leopard Racing": "#ffd700",
    "Rivacold Snipers Team": "#c02e2e",
    "SIC58 Squadra Corse": "#cc0000",
    # Moto3
    "CIP Green Power": "#2e8b57",
    "LEVEL UP - MTA": "#003366",
    "CODE Motorsports": "#cc0000",
    "Honda Team Asia": "#a5a5a5",
    "REDS Fantic Racing": "#cc0000",
    "Liqui Moly Dynavolt Intact GP Moto3": "#004d99",
}


def _pts_for_position(pos: int, session_type: str) -> int:
    if session_type in ("SPR", "S"):
        return SPRINT_POINTS.get(pos, 0)
    return RACE_POINTS.get(pos, 0)


# ── Session Analytics ──

@router.get("/sessions/{session_id}/analytics")
async def get_session_analytics(
    session_id: str,
    db: AsyncSession = Depends(get_session),
):
    """Best laps, top speeds, and gap analysis for a session."""
    res = await db.execute(
        select(Result).where(Result.session_id == session_id)
        .order_by(Result.position.nulls_last())
    )
    results = res.scalars().all()
    if not results:
        return {"error": "No results"}

    # Best laps (sorted by best_lap_time)
    best_laps = []
    # Top speeds
    top_speeds = []
    # Gaps to leader
    gaps = []

    for r in results:
        if r.best_lap_time:
            best_laps.append({
                "position": r.position,
                "rider_name": r.rider_name,
                "rider_number": r.rider_number,
                "rider_country": r.rider_country,
                "best_lap_time": r.best_lap_time,
                "best_lap_number": r.best_lap_number,
                "team_name": r.team_name,
                "constructor_name": r.constructor_name,
            })
        if r.top_speed:
            top_speeds.append({
                "position": r.position,
                "rider_name": r.rider_name,
                "rider_number": r.rider_number,
                "rider_country": r.rider_country,
                "top_speed": r.top_speed,
                "team_name": r.team_name,
                "constructor_name": r.constructor_name,
            })
        if r.position and r.position > 0:
            gaps.append({
                "position": r.position,
                "rider_name": r.rider_name,
                "rider_number": r.rider_number,
                "rider_country": r.rider_country,
                "team_name": r.team_name,
                "constructor_name": r.constructor_name,
                "total_time": r.total_time,
                "gap_first": r.gap_first,
                "gap_prev": r.gap_prev,
                "total_laps": r.total_laps,
                "status": r.status,
            })

    # Sort best_laps by time ascending
    def _parse_lap(lap_str):
        try:
            parts = lap_str.replace(":", " ").replace(".", " ").split()
            if len(parts) == 3:
                m, s, ms = parts
                return int(m) * 60 + int(s) + int(f"0.{ms}") if ms else 0
            elif len(parts) == 2:
                m, s = parts
                if "." in s:
                    sec, frac = s.split(".")
                    return int(m) * 60 + int(sec) + int(frac) / (10 ** len(frac)) if frac else int(m) * 60 + int(sec)
                return int(m) * 60 + int(s)
        except (ValueError, IndexError):
            return 999999
    best_laps.sort(key=lambda x: _parse_lap(x["best_lap_time"]))
    # Assign rank
    for i, bl in enumerate(best_laps, 1):
        bl["rank"] = i

    # Sort top speeds descending
    top_speeds.sort(key=lambda x: x["top_speed"], reverse=True)
    for i, ts in enumerate(top_speeds, 1):
        ts["rank"] = i

    # Get session info for weather
    sess_res = await db.execute(
        select(MotoSession).where(MotoSession.id == session_id)
    )
    sess = sess_res.scalar_one_or_none()

    weather = None
    if sess:
        weather = {
            "track_condition": sess.track_condition,
            "air_temp": sess.air_temp,
            "ground_temp": sess.ground_temp,
            "humidity": sess.humidity,
            "weather": sess.weather,
        }

    return {
        "session_id": session_id,
        "session_type": sess.type if sess else None,
        "total_riders": len(results),
        "best_laps": best_laps,
        "top_speeds": top_speeds,
        "gaps": gaps,
        "weather": weather,
    }


# ── Rider Season Progress ──

@router.get("/riders/{rider_id}/progress")
async def get_rider_progress(
    rider_id: str,
    year: int = Query(2026),
    db: AsyncSession = Depends(get_session),
):
    """Track a rider's performance across the season (race by race)."""
    # Get all race sessions for the year
    race_sessions = await db.execute(
        text("""
            SELECT s.id, s.type, s.event_id, e.round, e.short_name, e.date_start, e.circuit_name
            FROM sessions s
            JOIN events e ON e.id = s.event_id
            WHERE e.season_year = :year AND s.type IN ('RAC', 'SPR')
            ORDER BY e.round, s.date
        """),
        {"year": year}
    )
    sessions = race_sessions.fetchall()

    progress = []
    total_points = 0

    for s in sessions:
        res = await db.execute(
            select(Result).where(
                Result.session_id == s.id,
                Result.rider_id == rider_id,
            )
        )
        r = res.scalar_one_or_none()
        if not r:
            continue

        pts = _pts_for_position(r.position, s.type) if r.position and r.position > 0 else 0
        total_points += pts

        progress.append({
            "round": s.round,
            "event": s.short_name,
            "event_name": s.circuit_name,
            "date": s.date_start,
            "session_type": s.type,
            "session_label": "Race" if s.type == "RAC" else "Sprint",
            "position": r.position,
            "points": pts,
            "total_points": total_points,
            "best_lap_time": r.best_lap_time,
            "top_speed": r.top_speed,
            "total_laps": r.total_laps,
            "gap_first": r.gap_first,
            "status": r.status,
        })

    return {
        "rider_id": rider_id,
        "total_points": total_points,
        "races": progress,
    }


# ── Championship race-by-race breakdown ──

@router.get("/championship/breakdown")
async def get_championship_breakdown(
    year: int = Query(2026),
    category: Optional[str] = Query(None),
    top_n: int = Query(10, description="Top N riders to include"),
    db: AsyncSession = Depends(get_session),
):
    """Championship breakdown showing each rider's points per race."""
    # Get top N riders from standings
    q = select(RiderStanding).where(RiderStanding.season_year == year)
    if category:
        q = q.where(RiderStanding.category_id == category)
    q = q.order_by(RiderStanding.points.desc()).limit(top_n)
    standings_res = await db.execute(q)
    riders = standings_res.scalars().all()

    if not riders:
        return {"riders": [], "races": []}

    # Get all race events
    events_res = await db.execute(
        text("""
            SELECT DISTINCT e.id, e.round, e.short_name, e.circuit_name, e.date_start
            FROM events e
            JOIN sessions s ON s.event_id = e.id
            WHERE e.season_year = :year AND s.type IN ('RAC', 'SPR')
            ORDER BY e.round
        """),
        {"year": year}
    )
    events = events_res.fetchall()

    # For each rider, get results per event
    rider_data = []
    for rider in riders:
        results_by_event = {}
        for ev in events:
            # Get all sessions for this event
            sess_res = await db.execute(
                text("""
                    SELECT s.id, s.type FROM sessions s
                    WHERE s.event_id = :eid AND s.type IN ('RAC', 'SPR')
                """),
                {"eid": ev.id}
            )
            sess_list = sess_res.fetchall()

            event_pts = 0
            event_pos = None
            for sess_row in sess_list:
                res = await db.execute(
                    select(Result).where(
                        Result.session_id == sess_row.id,
                        Result.rider_id == rider.rider_id,
                    )
                )
                r = res.scalar_one_or_none()
                if r and r.position and r.position > 0:
                    pts = _pts_for_position(r.position, sess_row.type)
                    event_pts += pts
                    if sess_row.type == "RAC":
                        event_pos = r.position

            results_by_event[ev.round] = {
                "points": event_pts,
                "position": event_pos,
            }

        rider_data.append({
            "rider_id": rider.rider_id,
            "rider_name": rider.rider_name,
            "rider_number": rider.rider_number,
            "rider_country": rider.rider_country,
            "team_name": rider.team_name,
            "constructor_name": rider.constructor_name,
            "total_points": rider.points,
            "results": results_by_event,
        })

    races_list = [
        {
            "round": ev.round,
            "short_name": ev.short_name,
            "circuit_name": ev.circuit_name,
            "date_start": ev.date_start,
        }
        for ev in events
    ]

    return {
        "year": year,
        "races": races_list,
        "riders": rider_data,
    }


# ── Team Detail ──

@router.get("/teams/detail")
async def get_teams_detail(
    year: int = Query(2026),
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_session),
):
    """Get teams with riders and constructor standings info."""
    # Get team names from session drivers
    team_query = text(f"""
        SELECT DISTINCT
            r.team_id,
            r.team_name,
            r.constructor_name
        FROM results r
        JOIN sessions s ON s.id = r.session_id
        JOIN events e ON e.id = s.event_id
        WHERE e.season_year = :year
          { 'AND s.category_id = :cat' if category else '' }
        ORDER BY r.team_name
    """)
    team_params = {"year": year}
    if category:
        team_params["cat"] = category
    team_res = await db.execute(team_query, team_params)
    teams_raw = team_res.fetchall()

    # Get constructor standings
    cs_q = select(ConstructorStanding).where(ConstructorStanding.season_year == year)
    if category:
        cs_q = cs_q.where(ConstructorStanding.category_id == category)
    cs_q = cs_q.order_by(ConstructorStanding.points.desc())
    cs_res = await db.execute(cs_q)
    constructor_standings = {cs.constructor_name: cs.points for cs in cs_res.scalars()}

    # Get rider standings for each team
    rs_q = select(RiderStanding).where(RiderStanding.season_year == year)
    if category:
        rs_q = rs_q.where(RiderStanding.category_id == category)
    rs_q = rs_q.order_by(RiderStanding.points.desc())
    rs_res = await db.execute(rs_q)
    all_riders = rs_res.scalars().all()

    # Group riders by team_name
    from collections import defaultdict
    riders_by_team = defaultdict(list)
    for r in all_riders:
        riders_by_team[r.team_name].append({
            "rider_id": r.rider_id,
            "rider_name": r.rider_name,
            "rider_number": r.rider_number,
            "rider_country": r.rider_country,
            "points": r.points,
            "position": r.position,
        })

    # Group by constructor
    teams_by_constructor = defaultdict(list)
    for t in teams_raw:
        teams_by_constructor[t.constructor_name or t.team_name].append(t)

    teams_list = []
    seen = set()
    for t in teams_raw:
        key = f"{t.team_name}_{t.constructor_name}"
        if key in seen:
            continue
        seen.add(key)

        constr = t.constructor_name or "Unknown"
        riders = riders_by_team.get(t.team_name, [])
        # If no riders found by team_name, try by constructor
        if not riders:
            for team_name, rlist in riders_by_team.items():
                if constr in team_name or team_name in constr:
                    riders = rlist
                    break

        teams_list.append({
            "team_id": t.team_id,
            "team_name": t.team_name,
            "constructor_name": constr,
            "color": TEAM_COLORS.get(t.team_name, CONSTRUCTOR_COLORS.get(constr, "#666")),
            "constructor_points": constructor_standings.get(constr, 0),
            "riders": riders,
            "rider_count": len(riders),
        })

    return teams_list


# ── Season Summary Stats ──

@router.get("/season/stats")
async def get_season_stats(
    year: int = Query(2026),
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_session),
):
    """Season statistics: most wins, podiums, fastest laps, top speeds."""
    # Get all race sessions (RAC, SPR) for wins/podiums
    sess_q = text("""
        SELECT s.id, s.type, e.round
        FROM sessions s
        JOIN events e ON e.id = s.event_id
        WHERE e.season_year = :year AND s.type IN ('RAC', 'SPR')
          AND (:cat IS NULL OR s.category_id = :cat)
        ORDER BY e.round, s.date
    """)
    sess_res = await db.execute(sess_q, {"year": year, "cat": category})
    sessions = sess_res.fetchall()

    # Get all sessions (including FP, Q) for best lap / top speed data
    all_sess_q = text("""
        SELECT s.id, s.type, e.round
        FROM sessions s
        JOIN events e ON e.id = s.event_id
        WHERE e.season_year = :year
          AND (:cat IS NULL OR s.category_id = :cat)
        ORDER BY e.round, s.date
    """)
    all_sess_res = await db.execute(all_sess_q, {"year": year, "cat": category})
    all_sessions = all_sess_res.fetchall()

    from collections import defaultdict, Counter
    wins = Counter()
    podiums = Counter()
    poles = Counter()
    fastest_laps = Counter()
    top_speeds = defaultdict(float)
    rider_info = {}

    for s in sessions:
        # Get results
        res = await db.execute(
            select(Result).where(Result.session_id == s.id)
            .order_by(Result.position.nulls_last())
        )
        results = res.scalars().all()
        if not results:
            continue

        # Pole (P1 in qualifying — approximate via RAC/SPR P1)
        # Winner
        if results and results[0].position == 1:
            winner = results[0]
            wins[winner.rider_id] += 1
            rider_info[winner.rider_id] = {
                "name": winner.rider_name,
                "number": winner.rider_number,
                "country": winner.rider_country,
                "constructor": winner.constructor_name,
            }

        # Podiums (top 3)
        for r in results[:3]:
            if r.position and r.position <= 3:
                podiums[r.rider_id] += 1
                rider_info[r.rider_id] = {
                    "name": r.rider_name,
                    "number": r.rider_number,
                    "country": r.rider_country,
                    "constructor": r.constructor_name,
                }

        # Fastest lap
        session_best_lap = None
        for r in results:
            if r.best_lap_time and (session_best_lap is None or r.best_lap_time < session_best_lap):
                session_best_lap = r.best_lap_time

        for r in results:
            if r.best_lap_time == session_best_lap:
                fastest_laps[r.rider_id] += 1
                rider_info[r.rider_id] = {
                    "name": r.rider_name,
                    "number": r.rider_number,
                    "country": r.rider_country,
                    "constructor": r.constructor_name,
                }
                break

    # Fastest laps & top speeds from ALL sessions (FP/Q often have data)
    for s in all_sessions:
        res2 = await db.execute(
            select(Result).where(Result.session_id == s.id)
        )
        results2 = res2.scalars().all()
        if not results2:
            continue

        session_best = None
        for r in results2:
            if r.best_lap_time and (session_best is None or r.best_lap_time < session_best):
                session_best = r.best_lap_time

        for r in results2:
            if r.best_lap_time == session_best:
                fastest_laps[r.rider_id] += 1
                rider_info[r.rider_id] = {
                    "name": r.rider_name,
                    "number": r.rider_number,
                    "country": r.rider_country,
                    "constructor": r.constructor_name,
                }
                break

        for r in results2:
            if r.top_speed and r.top_speed > top_speeds.get(r.rider_id, 0):
                top_speeds[r.rider_id] = r.top_speed
                rider_info[r.rider_id] = {
                    "name": r.rider_name,
                    "number": r.rider_number,
                    "country": r.rider_country,
                    "constructor": r.constructor_name,
                }

    return {
        "wins": [
            {"rider_id": rid, **rider_info.get(rid, {}), "count": cnt}
            for rid, cnt in wins.most_common(10)
        ],
        "podiums": [
            {"rider_id": rid, **rider_info.get(rid, {}), "count": cnt}
            for rid, cnt in podiums.most_common(10)
        ],
        "fastest_laps": [
            {"rider_id": rid, **rider_info.get(rid, {}), "count": cnt}
            for rid, cnt in fastest_laps.most_common(10)
        ],
        "top_speeds": sorted(
            [{"rider_id": rid, **rider_info.get(rid, {}), "top_speed": spd}
             for rid, spd in top_speeds.items()],
            key=lambda x: -x["top_speed"]
        )[:10],
    }


# ── Season Progression (multi-rider line chart) ──

@router.get("/season/progression")
async def get_season_progression(
    year: int = Query(2026),
    category: Optional[str] = Query(None),
    top_n: int = Query(15, description="Top N riders"),
    db: AsyncSession = Depends(get_session),
):
    """Cumulative points per rider across every round. Perfect for a multi-line chart."""
    # Get all rounds with RAC/SPR sessions
    rounds_raw = await db.execute(
        text("""
            SELECT DISTINCT e.id, e.round, e.short_name, e.circuit_name, e.date_start
            FROM events e
            JOIN sessions s ON s.id IN (
                SELECT id FROM sessions WHERE event_id = e.id AND type IN ('RAC', 'SPR')
            )
            WHERE e.season_year = :year
            ORDER BY e.round
        """),
        {"year": year},
    )
    rounds = rounds_raw.fetchall()
    if not rounds:
        return {"rounds": [], "riders": []}

    # Get top N rider IDs from standings
    rider_q = select(RiderStanding.rider_id, RiderStanding.rider_name,
                     RiderStanding.constructor_name, RiderStanding.points,
                     RiderStanding.team_name, RiderStanding.rider_number)
    if category:
        rider_q = rider_q.where(RiderStanding.category_id == category)
    rider_q = rider_q.where(RiderStanding.season_year == year)
    rider_q = rider_q.order_by(RiderStanding.points.desc()).limit(top_n)
    top_riders = (await db.execute(rider_q)).fetchall()

    # For each rider, compute cumulative points per round
    rider_progress = []
    for r in top_riders:
        cum = 0
        pts_by_round = {}
        for ev in rounds:
            # Get results for this rider in all RAC/SPR sessions for this event
            sess_res = await db.execute(
                text("""
                    SELECT s.type, res.position
                    FROM sessions s
                    JOIN results res ON res.session_id = s.id
                    WHERE s.event_id = :eid AND s.type IN ('RAC', 'SPR')
                      AND res.rider_id = :rid
                """),
                {"eid": ev.id, "rid": r.rider_id},
            )
            sessions_data = sess_res.fetchall()
            event_pts = 0
            for sd in sessions_data:
                event_pts += _pts_for_position(sd.position, sd.type) if sd.position and sd.position > 0 else 0
            cum += event_pts
            pts_by_round[ev.round] = cum

        rider_progress.append({
            "rider_id": r.rider_id,
            "rider_name": r.rider_name,
            "rider_number": r.rider_number,
            "constructor_name": r.constructor_name,
            "team_name": r.team_name,
            "total_points": r.points,
            "cumulative": [pts_by_round.get(ev.round, 0) for ev in rounds],
        })

    return {
        "year": year,
        "rounds": [
            {
                "round": ev.round,
                "short_name": ev.short_name,
                "circuit_name": ev.circuit_name,
                "date_start": ev.date_start,
            }
            for ev in rounds
        ],
        "riders": rider_progress,
    }


# ── Teammate Battle ──

@router.get("/teammate-battle")
async def get_teammate_battle(
    year: int = Query(2026),
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_session),
):
    """Head-to-head comparison between teammates (same team)."""
    from collections import defaultdict, Counter

    # Get all riders in standings
    rider_q = select(RiderStanding).where(RiderStanding.season_year == year)
    if category:
        rider_q = rider_q.where(RiderStanding.category_id == category)
    rider_q = rider_q.order_by(RiderStanding.points.desc())
    riders = (await db.execute(rider_q)).scalars().all()
    if not riders:
        return {"year": year, "battles": [], "total": 0}

    # Group by team (actual teammates)
    by_team = defaultdict(list)
    for r in riders:
        by_team[r.team_name or r.constructor_name].append(r)

    # Get all RAC/SPR session IDs for the year in one query
    sess_res = await db.execute(
        text("""
            SELECT s.id, s.type, e.round, e.short_name AS event
            FROM sessions s
            JOIN events e ON e.id = s.event_id
            WHERE e.season_year = :year AND s.type IN ('RAC', 'SPR')
            ORDER BY e.round, s.date
        """),
        {"year": year},
    )
    all_sessions = sess_res.fetchall()
    if not all_sessions:
        return {"year": year, "battles": [], "total": 0}

    session_ids = [s.id for s in all_sessions]

    # Bulk-fetch all results for these sessions
    all_results = await db.execute(
        select(Result).where(
            Result.session_id.in_(session_ids),
            Result.position.isnot(None),
            Result.position > 0,
        )
    )
    results_list = all_results.scalars().all()

    # Index results by (session_id, rider_id)
    results_by_sess_rider = {}
    for r in results_list:
        results_by_sess_rider[(r.session_id, r.rider_id)] = r

    # Also index rider standings by rider_id
    standing_map = {r.rider_id: r for r in riders}

    # For each team with 2+ riders, compute head-to-head
    battles = []
    for team, rider_list in sorted(by_team.items()):
        if len(rider_list) < 2:
            continue

        rider_ids = [r.rider_id for r in rider_list]

        # Per-rider stats
        rider_stats = {}
        for r in rider_list:
            sessions_data = [
                results_by_sess_rider.get((s.id, r.rider_id))
                for s in all_sessions
            ]
            sessions_data = [x for x in sessions_data if x]

            race_count = len(sessions_data)
            wins = sum(1 for x in sessions_data if x.position == 1)
            podiums = sum(1 for x in sessions_data if x.position and x.position <= 3)
            avg_pos = round(sum(x.position for x in sessions_data if x.position) / max(race_count, 1), 2) if race_count else 0

            rider_stats[r.rider_id] = {
                "rider_id": r.rider_id,
                "rider_name": r.rider_name,
                "rider_number": r.rider_number,
                "rider_country": r.rider_country,
                "points": r.points,
                "position": r.position,
                "races": race_count,
                "wins": wins,
                "podiums": podiums,
                "avg_position": avg_pos,
            }

        # Head-to-head between pairs
        h2h_list = []
        for i in range(len(rider_ids)):
            for j in range(i + 1, len(rider_ids)):
                a_id, b_id = rider_ids[i], rider_ids[j]
                a_wins = b_wins = 0
                for s in all_sessions:
                    a_r = results_by_sess_rider.get((s.id, a_id))
                    b_r = results_by_sess_rider.get((s.id, b_id))
                    if a_r and b_r and a_r.position and b_r.position:
                        if a_r.position < b_r.position:
                            a_wins += 1
                        elif b_r.position < a_r.position:
                            b_wins += 1
                total = a_wins + b_wins
                if total > 0:
                    h2h_list.append({
                        "rider_a": rider_stats[a_id],
                        "rider_b": rider_stats[b_id],
                        "a_wins": a_wins,
                        "b_wins": b_wins,
                        "total_meetings": total,
                        "a_pct": round(a_wins / total * 100, 1),
                        "b_pct": round(b_wins / total * 100, 1),
                    })

        if h2h_list:
            # Get constructor for color from first rider
            constr = rider_list[0].constructor_name or ""
            color = CONSTRUCTOR_COLORS.get(constr, "#666")
            battles.append({
                "team_name": team,
                "constructor_name": constr,
                "color": color,
                "riders": [rider_stats[rid] for rid in rider_ids],
                "head_to_head": h2h_list,
            })

    return {"year": year, "battles": battles, "total": len(battles)}


# ── Rider Comparison ──

@router.get("/riders/compare")
async def compare_riders(
    rider_a: str = Query(..., description="First rider ID"),
    rider_b: str = Query(..., description="Second rider ID"),
    year: int = Query(2026),
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_session),
):
    """Side-by-side comparison of two riders across the season."""
    # Get standings info for both riders
    async def get_standing(rid):
        q = select(RiderStanding).where(
            RiderStanding.rider_id == rid,
            RiderStanding.season_year == year,
        )
        if category:
            q = q.where(RiderStanding.category_id == category)
        return (await db.execute(q)).scalar_one_or_none()

    sa = await get_standing(rider_a)
    sb = await get_standing(rider_b)
    if not sa or not sb:
        return {"error": "Rider not found"}

    # Get all RAC/SPR sessions
    sess_res = await db.execute(
        text("""
            SELECT s.id, s.type, e.round, e.short_name
            FROM sessions s
            JOIN events e ON e.id = s.event_id
            WHERE e.season_year = :year AND s.type IN ('RAC', 'SPR')
            ORDER BY e.round, s.date
        """),
        {"year": year},
    )
    sessions = sess_res.fetchall()

    sessions_a = []
    sessions_b = []
    a_total = 0
    b_total = 0
    a_dnf = 0
    b_dnf = 0
    a_best_lap = None
    b_best_lap = None
    a_top_speed = 0
    b_top_speed = 0

    for s in sessions:
        a_res = await db.execute(
            select(Result).where(Result.session_id == s.id, Result.rider_id == rider_a)
        )
        b_res = await db.execute(
            select(Result).where(Result.session_id == s.id, Result.rider_id == rider_b)
        )
        ar = a_res.scalar_one_or_none()
        br = b_res.scalar_one_or_none()

        if ar:
            pts = _pts_for_position(ar.position, s.type) if ar.position and ar.position > 0 else 0
            a_total += pts
            if not ar.position or ar.position == 0:
                a_dnf += 1
            if ar.best_lap_time and (a_best_lap is None or ar.best_lap_time < a_best_lap):
                a_best_lap = ar.best_lap_time
            if ar.top_speed and ar.top_speed > a_top_speed:
                a_top_speed = ar.top_speed
            sessions_a.append({
                "round": s.round,
                "event": s.short_name,
                "type": s.type,
                "position": ar.position,
                "points": pts,
                "best_lap": ar.best_lap_time,
                "top_speed": ar.top_speed,
                "status": ar.status,
            })
        if br:
            pts = _pts_for_position(br.position, s.type) if br.position and br.position > 0 else 0
            b_total += pts
            if not br.position or br.position == 0:
                b_dnf += 1
            if br.best_lap_time and (b_best_lap is None or br.best_lap_time < b_best_lap):
                b_best_lap = br.best_lap_time
            if br.top_speed and br.top_speed > b_top_speed:
                b_top_speed = br.top_speed
            sessions_b.append({
                "round": s.round,
                "event": s.short_name,
                "type": s.type,
                "position": br.position,
                "points": pts,
                "best_lap": br.best_lap_time,
                "top_speed": br.top_speed,
                "status": br.status,
            })

    # Count head-to-head
    a_wins = 0
    b_wins = 0
    ties = 0
    common = 0
    for ar in sessions_a:
        for br in sessions_b:
            if ar["round"] == br["round"] and ar["type"] == br["type"]:
                common += 1
                if ar["position"] and br["position"]:
                    if ar["position"] < br["position"]:
                        a_wins += 1
                    elif br["position"] < ar["position"]:
                        b_wins += 1
                    else:
                        ties += 1
                break

    return {
        "rider_a": {
            "rider_id": sa.rider_id,
            "rider_name": sa.rider_name,
            "rider_number": sa.rider_number,
            "rider_country": sa.rider_country,
            "constructor_name": sa.constructor_name,
            "team_name": sa.team_name,
            "total_points": sa.points,
            "races": len(sessions_a),
            "dnfs": a_dnf,
            "best_lap_time": a_best_lap,
            "top_speed": a_top_speed,
            "avg_position": round(
                sum(s["position"] for s in sessions_a if s["position"]), 2
            ) / max(len([s for s in sessions_a if s["position"]]), 1),
            "sessions": sessions_a,
        },
        "rider_b": {
            "rider_id": sb.rider_id,
            "rider_name": sb.rider_name,
            "rider_number": sb.rider_number,
            "rider_country": sb.rider_country,
            "constructor_name": sb.constructor_name,
            "team_name": sb.team_name,
            "total_points": sb.points,
            "races": len(sessions_b),
            "dnfs": b_dnf,
            "best_lap_time": b_best_lap,
            "top_speed": b_top_speed,
            "avg_position": round(
                sum(s["position"] for s in sessions_b if s["position"]), 2
            ) / max(len([s for s in sessions_b if s["position"]]), 1),
            "sessions": sessions_b,
        },
        "head_to_head": {
            "common_sessions": common,
            "a_wins": a_wins,
            "b_wins": b_wins,
            "ties": ties,
        },
    }


# ── CSV Export ──

@router.get("/sessions/{session_id}/export/csv")
async def export_session_csv(
    session_id: str,
    db: AsyncSession = Depends(get_session),
):
    """Export session results as CSV."""
    res = await db.execute(
        select(Result).where(Result.session_id == session_id)
        .order_by(Result.position.nulls_last())
    )
    results = res.scalars().all()

    if not results:
        return FastResponse("No results", media_type="text/csv", status_code=404)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Position", "Rider ID", "Rider Name", "Rider Number", "Rider Country",
        "Team Name", "Constructor", "Total Time", "Gap to First", "Gap to Previous",
        "Best Lap Time", "Best Lap Number", "Total Laps", "Top Speed (km/h)", "Status",
    ])
    for r in results:
        writer.writerow([
            r.position, r.rider_id, r.rider_name, r.rider_number, r.rider_country,
            r.team_name, r.constructor_name, r.total_time, r.gap_first, r.gap_prev,
            r.best_lap_time, r.best_lap_number, r.total_laps, r.top_speed, r.status,
        ])

    filename = f"motogp-session-{session_id[:8]}.csv"
    return FastResponse(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── Circuits ──

@router.get("/circuits")
async def get_circuits(
    year: int = Query(2026),
    db: AsyncSession = Depends(get_session),
):
    """Get circuit information from events."""
    res = await db.execute(
        text("""
            SELECT DISTINCT e.circuit_name, e.country, e.country_iso, e.short_name,
                   e.date_start, e.status
            FROM events e
            WHERE e.season_year = :year AND e.circuit_name != ''
            ORDER BY e.round
        """),
        {"year": year},
    )
    circuits = res.fetchall()

    return [
        {
            "name": c.circuit_name,
            "country": c.country,
            "country_iso": c.country_iso,
            "event": c.short_name,
            "date": c.date_start,
            "status": c.status,
            "flag": COUNTRY_FLAGS.get(c.country_iso, ""),
        }
        for c in circuits
    ]


# ── Rider Form ──

@router.get("/riders/form")
async def get_rider_form(
    rider_id: str = Query(..., description="Rider UUID"),
    year: int = Query(2026),
    limit: int = Query(5, ge=2, le=20),
    db: AsyncSession = Depends(get_session),
):
    """Recent race/sprint form for a rider: last N results with trend."""
    res = await db.execute(
        text("""
            SELECT e.round, e.short_name, e.country_iso, e.date_start,
                   s.id AS session_id, s.type, s.number, r.position, r.total_laps,
                   r.best_lap_time, r.top_speed, r.status,
                   r.total_time, r.gap_first
            FROM results r
            JOIN sessions s ON s.id = r.session_id
            JOIN events e ON e.id = s.event_id
            WHERE r.rider_id = :rid AND e.season_year = :year
              AND s.type IN ('RAC', 'SPR')
            ORDER BY e.round DESC, s.date DESC
            LIMIT :lim
        """),
        {"rid": rider_id, "year": year, "lim": limit},
    )
    rows = res.fetchall()
    if not rows:
        return {"rider_id": rider_id, "year": year, "races": []}

    # Re-sort chronologically (was DESC for LIMIT)
    rows = list(reversed(rows))

    results_list = []
    for r in rows:
        pts = _pts_for_position(r.position, r.type)
        session_label = r.type
        if r.number:
            session_label = f"{r.type}#{r.number}"
        results_list.append({
            "round": r.round,
            "event": r.short_name,
            "country_iso": r.country_iso,
            "flag": COUNTRY_FLAGS.get(r.country_iso, ""),
            "date": r.date_start,
            "session_type": r.type,
            "session_number": r.number,
            "session_label": session_label,
            "position": r.position,
            "points": pts,
            "total_laps": r.total_laps,
            "best_lap_time": r.best_lap_time,
            "top_speed": r.top_speed,
            "status": r.status,
            "total_time": r.total_time,
            "gap_first": r.gap_first,
        })

    # Trend: position trajectory
    positions = [r["position"] for r in results_list]
    trend = "stable"
    if len(positions) >= 3:
        first_half = positions[:len(positions)//2]
        second_half = positions[len(positions)//2:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        if avg_second < avg_first - 1:
            trend = "improving"
        elif avg_second > avg_first + 1:
            trend = "declining"

    return {
        "rider_id": rider_id,
        "year": year,
        "total_races": len(results_list),
        "trend": trend,
        "races": results_list,
    }


# ── Speed Traps ──

@router.get("/sessions/{session_id}/speed-traps")
async def get_speed_traps(
    session_id: str,
    db: AsyncSession = Depends(get_session),
):
    """Top speed ranking per session."""
    res = await db.execute(
        select(Result).where(
            Result.session_id == session_id,
            Result.top_speed.isnot(None),
            Result.top_speed > 0,
        ).order_by(Result.top_speed.desc())
    )
    results = res.scalars().all()

    if not results:
        return {"session_id": session_id, "drivers": []}

    # Get session info
    sess_res = await db.execute(
        select(MotoSession).where(MotoSession.id == session_id)
    )
    sess = sess_res.scalar_one_or_none()

    drivers = []
    for i, r in enumerate(results, 1):
        drivers.append({
            "rank": i,
            "rider_id": r.rider_id,
            "rider_name": r.rider_name,
            "rider_number": r.rider_number,
            "rider_country": r.rider_country,
            "flag": COUNTRY_FLAGS.get(r.rider_country, ""),
            "team_name": r.team_name,
            "constructor_name": r.constructor_name,
            "top_speed": r.top_speed,
            "position": r.position,
            "total_laps": r.total_laps,
        })

    return {
        "session_id": session_id,
        "session_type": sess.type if sess else None,
        "total_riders": len(drivers),
        "fastest_speed": drivers[0]["top_speed"] if drivers else None,
        "slowest_speed": drivers[-1]["top_speed"] if drivers else None,
        "avg_speed": round(sum(d["top_speed"] for d in drivers) / len(drivers), 1) if drivers else 0,
        "drivers": drivers,
    }


# ── Rider Season Stats ──

@router.get("/riders/stats")
async def get_rider_season_stats(
    year: int = Query(2026),
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_session),
):
    """Aggregate season stats for all riders: avg position, podiums, DNFs, etc."""
    # Build query with optional category filter
    cat_join = ""
    cat_param = {}
    if category:
        cat_join = "JOIN categories c ON c.id = s.category_id"
        cat_param["cat"] = category
    res = await db.execute(
        text(f"""
            SELECT r.rider_id, r.rider_name, r.rider_number, r.rider_country,
                   r.team_name, r.constructor_name,
                   r.position, r.top_speed, r.status, r.total_laps,
                   e.round, s.type
            FROM results r
            JOIN sessions s ON s.id = r.session_id
            JOIN events e ON e.id = s.event_id
            {cat_join}
            WHERE e.season_year = :year
              AND s.type IN ('RAC', 'SPR')
              { 'AND c.id = :cat' if category else '' }
        """),
        {"year": year, **cat_param},
    )
    rows = res.fetchall()
    if not rows:
        return {"year": year, "riders": []}

    from collections import defaultdict

    rider_data = defaultdict(lambda: {
        "races": 0, "points": 0, "wins": 0, "podiums": 0,
        "top5": 0, "dnf": 0, "positions": [],
        "team_name": "", "constructor_name": "",
        "rider_number": None, "rider_country": "",
        "best_lap_times": [], "top_speeds": [],
    })

    for r in rows:
        rid = r.rider_id
        rd = rider_data[rid]
        rd["rider_name"] = r.rider_name
        rd["rider_number"] = r.rider_number or rd["rider_number"]
        rd["rider_country"] = r.rider_country or rd["rider_country"]
        rd["team_name"] = r.team_name or rd["team_name"]
        rd["constructor_name"] = r.constructor_name or rd["constructor_name"]

        if r.position and r.position > 0:
            rd["races"] += 1
            rd["positions"].append(r.position)
            pts = _pts_for_position(r.position, r.type)
            rd["points"] += pts
            if r.position == 1:
                rd["wins"] += 1
            if r.position <= 3:
                rd["podiums"] += 1
            if r.position <= 5:
                rd["top5"] += 1
        if r.status and "DNF" in str(r.status).upper():
            rd["dnf"] += 1

    # Build sorted list
    riders_list = []
    for rid, rd in rider_data.items():
        positions = rd["positions"]
        avg_pos = round(sum(positions) / len(positions), 1) if positions else None
        best_pos = min(positions) if positions else None
        riders_list.append({
            "rider_id": rid,
            "rider_name": rd["rider_name"],
            "rider_number": rd["rider_number"],
            "rider_country": rd["rider_country"],
            "flag": COUNTRY_FLAGS.get(rd["rider_country"], ""),
            "team_name": rd["team_name"],
            "constructor_name": rd["constructor_name"],
            "races": rd["races"],
            "points": rd["points"],
            "avg_position": avg_pos,
            "best_position": best_pos,
            "wins": rd["wins"],
            "podiums": rd["podiums"],
            "top5": rd["top5"],
            "dnf": rd["dnf"],
        })

    # Sort by points descending
    riders_list.sort(key=lambda x: -x["points"])

    return {
        "year": year,
        "total_riders": len(riders_list),
        "riders": riders_list,
    }
