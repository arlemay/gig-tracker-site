from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from .database import Base

# Association table: many-to-many (events <-> bands)
event_bands = Table(
    "event_bands",
    Base.metadata,
    Column("event_id", ForeignKey("events.id"), primary_key=True),
    Column("band_id", ForeignKey("bands.id"), primary_key=True),
)


class Band(Base):
    __tablename__ = "bands"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), unique=True, nullable=False)
    genre = Column(String(120), nullable=True)
    city = Column(String(120), nullable=True)  # e.g., Denpasar, Badung
    instagram = Column(String(255), nullable=True)
    youtube = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)


class Venue(Base):
    __tablename__ = "venues"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), unique=True, nullable=False)
    address = Column(String(255), nullable=True)
    district = Column(String(120), nullable=True)  # e.g., Denpasar Selatan
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    instagram = Column(String(255), nullable=True)
    website = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    starts_at = Column(DateTime, nullable=False)
    ends_at = Column(DateTime, nullable=True)
    venue_id = Column(Integer, ForeignKey("venues.id"), nullable=False)
    price = Column(String(60), nullable=True)  # e.g. "Presale 50k | OTS 80k"
    poster_url = Column(String(255), nullable=True)
    url = Column(String(255), nullable=True)

    venue = relationship("Venue")
    bands = relationship("Band", secondary=event_bands, backref="events")
