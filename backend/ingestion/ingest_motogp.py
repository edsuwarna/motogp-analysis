"""
MotoGP Analysis — Data ingestion from MotoGP pulselive API.
Optimized: fetches sequentially but with timeouts per call.
"""

import asyncio
import json
import time
from typing import Optional
import httpx
from sqlalchemy import select
from sqlalchemy import text

from backend.models.models import (
    Season, Category, Event, Session as MotoSession,
    Result, RiderStanding, ConstructorStanding, Team
)
from backend.core.database import async_session

BASE_URL = "https://api.motogp.pulselive.com/motogp/v1"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Origin": "https://www.motogp.com",
    "Referer": "https://www.motogp.com/",
}

# Session types relevant for standings
SCORING_SESSIONS = {"RAC", "SPR"}

# Points systems
RACE_POINTS = {1: 25, 2: 20, 3: 16, 4: 13, 5: 11, 6: 10, 7: 9, 8: 8, 9: 7,
               10: 6, 11: 5, 12: 4, 13: 3, 14: 2, 15: 1}
SPRINT_POINTS = {1: 12, 2: 9, 3: 7, 4: 6, 5: 5, 6: 4, 7: 3, 8: 2, 9: 1}


async def api_get(path: str, params: dict = None) -> Optional[dict | list]:
    url = f"{BASE_URL}{path}"
    async with httpx.AsyncClient(headers=HEADERS, timeout=httpx.Timeout(15.0)) as c:
        try:
            r = await c.get(url, params=params)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            print(f"  [API] Error {path}: {e}")
    return None


async def ingest_season(year: int):
    """Full ingestion for a season year."""
    t0 = time.time()
    print(f"\n{'='*50}")
    print(f"[Ingest] Starting MotoGP {year}")
    print(f"{'='*50}")

    # 1. Get season UUID
    seasons = await api_get("/results/seasons")
    season_uuid = None
    for s in seasons or []:
        if s["year"] == year:
            season_uuid = s["id"]
            break
    if not season_uuid:
        print(f"[Ingest] Season {year} not found!")
        return

    async with async_session() as db:
        # Save season
        await db.merge(Season(id=season_uuid, year=year, current=True))
        await db.commit()
        print(f"  ✅ Season {year} UUID: {season_uuid[:12]}...")

        # 2. Get categories
        cats = await api_get("/results/categories", {"seasonUuid": season_uuid})
        category_map = {}
        for c in cats or []:
            await db.merge(Category(
                id=c["id"], name=c["name"],
                legacy_id=c.get("legacy_id"), season_year=year
            ))
            category_map[c["id"]] = c["name"]
        await db.commit()
        print(f"  ✅ Categories: {len(category_map)} ({', '.join(category_map.values())})")

        # 3. Get events (skip test events)
        all_events = await api_get("/results/events", {"seasonUuid": season_uuid})
        gp_events = [e for e in all_events if not e.get("test")] if all_events else []
        gp_events.sort(key=lambda e: e.get("legacy_id", [{}])[0].get("eventId", 0) if e.get("legacy_id") else 0)
        print(f"  ✅ GP events: {len(gp_events)}")

        for round_num, ev in enumerate(gp_events, 1):
            eid = ev["id"]
            circuit = ev.get("circuit", {}) or {}
            country_data = ev.get("country", {}) or {}

            await db.merge(Event(
                id=eid, season_year=year, round=round_num,
                name=ev.get("name", ""), short_name=ev.get("short_name", ""),
                circuit_name=circuit.get("name", ""),
                country=country_data.get("name", ""),
                country_iso=country_data.get("iso", ""),
                date_start=ev.get("date_start", ""),
                date_end=ev.get("date_end", ""),
                sponsored_name=ev.get("sponsored_name", ""),
                status=ev.get("status", "SCHEDULED"),
            ))
            await db.commit()

            # 4. Sessions per category
            for cat_id, cat_name in category_map.items():
                if "MotoE" in cat_name:
                    continue
                await _ingest_sessions(db, eid, cat_id, round_num, year)

            print(f"  ✅ R{round_num:2d} {ev['short_name']:4s} {circuit.get('name',''):35s} {ev.get('status','')}")

        # 5. Teams
        await _ingest_teams(db, year, category_map)

        # 6. Build standings
        await _build_standings(db, year)

    elapsed = time.time() - t0
    print(f"\n  ✅ Done! ({elapsed:.0f}s)")
    print(f"{'='*50}\n")


async def _ingest_sessions(db, event_id: str, cat_id: str, round_num: int, year: int):
    """Fetch and save sessions + results for one event+category combo."""
    sessions = await api_get("/results/sessions", {
        "eventUuid": event_id, "categoryUuid": cat_id,
    })
    if not sessions:
        return

    for sess in sessions:
        sid = sess["id"]
        cond = sess.get("condition", {}) or {}

        await db.merge(MotoSession(
            id=sid, event_id=event_id, category_id=cat_id,
            type=sess.get("type", ""), number=sess.get("number"),
            date=sess.get("date", ""), status=sess.get("status", ""),
            track_condition=cond.get("track", ""),
            air_temp=cond.get("air", ""),
            ground_temp=cond.get("ground", ""),
            humidity=cond.get("humidity", ""),
            weather=cond.get("weather", ""),
        ))
        await db.commit()

        # Classification only for Race & Sprint
        sess_type = sess.get("type", "")
        if sess_type not in SCORING_SESSIONS:
            continue

        # Clear old results for this session before re-inserting
        await db.execute(
            text("DELETE FROM results WHERE session_id = :sid"),
            {"sid": sid}
        )

        cls = await api_get(f"/results/session/{sid}/classification")
        if not cls:
            continue

        for item in cls.get("classification", []):
            rider = item.get("rider", {}) or {}
            team = item.get("team", {}) or {}
            constructor = item.get("constructor", {}) or {}
            best = item.get("best_lap", {}) or {}
            gap = item.get("gap", {}) or {}
            country = rider.get("country", {}) or {}

            db.add(Result(
                session_id=sid, position=item.get("position"),
                rider_id=rider.get("id", ""),
                rider_name=rider.get("full_name", ""),
                rider_number=rider.get("number"),
                rider_country=country.get("iso", ""),
                team_id=team.get("id", ""),
                team_name=team.get("name", ""),
                constructor_name=constructor.get("name", ""),
                total_time=item.get("total_time", ""),
                gap_first=gap.get("first", ""),
                gap_prev=gap.get("prev", ""),
                best_lap_time=best.get("time", ""),
                best_lap_number=best.get("number"),
                total_laps=item.get("total_laps"),
                top_speed=item.get("top_speed"),
                status=item.get("status", ""),
            ))
        await db.commit()


async def _ingest_teams(db, year: int, category_map: dict):
    """Fetch teams with rider info."""
    for cat_id in category_map:
        teams = await api_get("/teams", {
            "categoryUuid": cat_id, "seasonYear": year,
        })
        if not teams:
            continue
        for t in teams:
            riders_json = json.dumps(t.get("riders", []))
            const = t.get("constructor", {}) or {}
            await db.merge(Team(
                id=t["id"], name=t.get("name", ""), season_year=year,
                constructor_name=const.get("name", ""),
                color=t.get("color", ""), text_color=t.get("text_color", ""),
                picture=t.get("picture", ""), riders_json=riders_json,
            ))
        await db.commit()
    print(f"  ✅ Teams saved")


async def _build_standings(db, year: int):
    """Compute rider & constructor standings from results."""
    # Clear old
    await db.execute(RiderStanding.__table__.delete().where(
        RiderStanding.season_year == year))
    await db.execute(ConstructorStanding.__table__.delete().where(
        ConstructorStanding.season_year == year))

    # Get all race/sprint sessions
    res = await db.execute(
        select(MotoSession, Event.round)
        .select_from(MotoSession)
        .join(Event, MotoSession.event_id == Event.id)
        .filter(
            Event.season_year == year,
            MotoSession.type.in_(["RAC", "SPR"]),
            MotoSession.category_id.isnot(None),
        )
        .order_by(Event.round, MotoSession.date)
    )
    scoring_sessions = res.all()

    rider_pts = {}
    constr_pts = {}

    for ms, rnd in scoring_sessions:
        r_res = await db.execute(
            select(Result).where(Result.session_id == ms.id)
            .order_by(Result.position)
        )
        results = r_res.scalars().all()
        points_map = SPRINT_POINTS if ms.type == "SPR" else RACE_POINTS

        for r in results:
            pts = points_map.get(r.position, 0)
            key = (r.rider_id, ms.category_id)
            if key not in rider_pts:
                rider_pts[key] = {
                    "name": r.rider_name, "num": r.rider_number,
                    "country": r.rider_country, "team": r.team_name,
                    "constructor": r.constructor_name, "total": 0,
                }
            rider_pts[key]["total"] += pts

            # Constructor points
            ckey = (r.constructor_name, ms.category_id, rnd)
            constr_pts[ckey] = constr_pts.get(ckey, 0) + pts

    # Save rider standings
    for pos, ((rid, cid), data) in enumerate(
        sorted(rider_pts.items(), key=lambda x: -x[1]["total"]), 1
    ):
        db.add(RiderStanding(
            season_year=year, category_id=cid, round=22,
            position=pos, rider_id=rid, rider_name=data["name"],
            rider_number=data["num"], rider_country=data["country"],
            team_name=data["team"], constructor_name=data["constructor"],
            points=data["total"],
        ))
    await db.commit()
    print(f"  ✅ Rider standings: {len(rider_pts)} riders")

    # Aggregate constructor points
    con_totals = {}
    for (con, cid, rnd), pts in constr_pts.items():
        key = (con, cid)
        con_totals[key] = con_totals.get(key, 0) + pts

    for pos, ((con, cid), total) in enumerate(
        sorted(con_totals.items(), key=lambda x: -x[1]), 1
    ):
        db.add(ConstructorStanding(
            season_year=year, category_id=cid, round=22,
            position=pos, constructor_name=con, points=total,
        ))
    await db.commit()
    print(f"  ✅ Constructor standings: {len(con_totals)} constructors")
