"""
MotoGP Analysis — Database setup (SQLite).
"""

import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from backend.models.models import Base

DB_PATH = os.getenv("MOTOGP_DB", os.path.join(os.path.dirname(__file__), "..", "..", "motogp.db"))
DB_URL = f"sqlite+aiosqlite:///{DB_PATH}"

engine = create_async_engine(DB_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def init_db():
    """Create tables if not exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session():
    async with async_session() as session:
        yield session
