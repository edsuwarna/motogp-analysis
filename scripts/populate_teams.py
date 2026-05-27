"""MotoGP Analysis — Data ingestion: populate teams table from results."""
import asyncio
from backend.core.database import async_session
from backend.models.models import Team


async def populate_teams():
    """Populate teams table from unique team data in results."""
    from sqlalchemy import text
    async with async_session() as db:
        # Get unique teams from results
        res = await db.execute(text("""
            SELECT DISTINCT r.team_id, r.team_name, r.constructor_name
            FROM results r
            ORDER BY r.team_name
        """))
        rows = res.fetchall()

        count = 0
        for row in rows:
            existing = await db.execute(
                text("SELECT id FROM teams WHERE id = :id"),
                {"id": row.team_id}
            )
            if existing.fetchone():
                continue
            await db.execute(
                text("""
                    INSERT INTO teams (id, name, constructor_name, season_year)
                    VALUES (:id, :name, :constructor, :year)
                """),
                {
                    "id": row.team_id,
                    "name": row.team_name,
                    "constructor": row.constructor_name,
                    "year": 2026,
                }
            )
            count += 1
        await db.commit()
        print(f"✅ Populated {count} teams")

if __name__ == "__main__":
    asyncio.run(populate_teams())
