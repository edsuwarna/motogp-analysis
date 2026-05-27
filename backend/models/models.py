"""
MotoGP Analysis — SQLAlchemy models for SQLite.
"""

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, ForeignKey, Text, create_engine
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Season(Base):
    __tablename__ = "seasons"
    id = Column(String(64), primary_key=True)
    year = Column(Integer, nullable=False)
    current = Column(Boolean, default=False)


class Category(Base):
    __tablename__ = "categories"
    id = Column(String(64), primary_key=True)
    name = Column(String(64), nullable=False)
    legacy_id = Column(Integer)
    season_year = Column(Integer, nullable=False)


class Event(Base):
    __tablename__ = "events"
    id = Column(String(64), primary_key=True)
    season_year = Column(Integer, nullable=False)
    round = Column(Integer)
    name = Column(String(200))
    short_name = Column(String(20))
    circuit_name = Column(String(200))
    circuit_image = Column(String(500))
    country = Column(String(100))
    country_iso = Column(String(10))
    date_start = Column(String(20))
    date_end = Column(String(20))
    sponsored_name = Column(String(300))
    status = Column(String(20), default="scheduled")
    sessions = relationship("Session", backref="event", cascade="all, delete-orphan")


class Session(Base):
    __tablename__ = "sessions"
    id = Column(String(64), primary_key=True)
    event_id = Column(String(64), ForeignKey("events.id"), nullable=False)
    category_id = Column(String(64), ForeignKey("categories.id"))
    type = Column(String(10))  # P=Practice, Q=Qualifying, R=Race, S=Sprint
    number = Column(Integer)
    date = Column(String(30))
    status = Column(String(20))
    track_condition = Column(String(50))
    air_temp = Column(String(10))
    ground_temp = Column(String(10))
    humidity = Column(String(10))
    weather = Column(String(50))
    results = relationship("Result", backref="session", cascade="all, delete-orphan")


class Result(Base):
    __tablename__ = "results"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), ForeignKey("sessions.id"), nullable=False)
    position = Column(Integer)
    rider_id = Column(String(64))
    rider_name = Column(String(200))
    rider_number = Column(Integer)
    rider_country = Column(String(10))
    team_id = Column(String(64))
    team_name = Column(String(200))
    constructor_name = Column(String(100))
    total_time = Column(String(50))
    gap_first = Column(String(50))
    gap_prev = Column(String(50))
    best_lap_time = Column(String(20))
    best_lap_number = Column(Integer)
    total_laps = Column(Integer)
    top_speed = Column(Float)
    status = Column(String(20))


class RiderStanding(Base):
    __tablename__ = "rider_standings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    season_year = Column(Integer, nullable=False)
    category_id = Column(String(64))
    round = Column(Integer)
    position = Column(Integer)
    rider_id = Column(String(64))
    rider_name = Column(String(200))
    rider_number = Column(Integer)
    rider_country = Column(String(10))
    team_name = Column(String(200))
    constructor_name = Column(String(100))
    points = Column(Float)


class ConstructorStanding(Base):
    __tablename__ = "constructor_standings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    season_year = Column(Integer, nullable=False)
    category_id = Column(String(64))
    round = Column(Integer)
    position = Column(Integer)
    constructor_name = Column(String(100))
    points = Column(Float)


class Team(Base):
    __tablename__ = "teams"
    id = Column(String(64), primary_key=True)
    name = Column(String(200))
    season_year = Column(Integer)
    constructor_name = Column(String(100))
    color = Column(String(10))
    text_color = Column(String(10))
    picture = Column(String(500))
    riders_json = Column(Text)  # JSON string of riders in this team
