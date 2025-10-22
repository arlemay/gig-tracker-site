# backend/schemas.py
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

# ---------- Bands ----------
class BandBase(BaseModel):
    name: str = Field(..., max_length=200)
    genre: Optional[str] = None
    city: Optional[str] = None
    instagram: Optional[str] = None
    youtube: Optional[str] = None
    description: Optional[str] = None

class BandCreate(BandBase):
    pass

class BandUpdate(BaseModel):
    name: Optional[str] = None
    genre: Optional[str] = None
    city: Optional[str] = None
    instagram: Optional[str] = None
    youtube: Optional[str] = None
    description: Optional[str] = None

class BandOut(BandBase):
    id: int
    class Config:
        from_attributes = True

# ---------- Venues ----------
class VenueBase(BaseModel):
    name: str
    address: Optional[str] = None
    district: Optional[str] = None
    lat: float
    lon: float
    instagram: Optional[str] = None
    website: Optional[str] = None
    notes: Optional[str] = None

class VenueCreate(VenueBase):
    pass

class VenueUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    district: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    instagram: Optional[str] = None
    website: Optional[str] = None
    notes: Optional[str] = None

class VenueOut(VenueBase):
    id: int
    class Config:
        from_attributes = True

# ---------- Events ----------
class EventBase(BaseModel):
    title: str
    starts_at: datetime
    ends_at: Optional[datetime] = None
    price: Optional[str] = None
    poster_url: Optional[str] = None
    url: Optional[str] = None
    venue_id: int
    band_ids: List[int] = []

class EventCreate(EventBase):
    pass

class EventUpdate(BaseModel):
    title: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    price: Optional[str] = None
    poster_url: Optional[str] = None
    url: Optional[str] = None
    venue_id: Optional[int] = None
    band_ids: Optional[List[int]] = None

class EventOut(BaseModel):
    id: int
    title: str
    starts_at: datetime
    ends_at: Optional[datetime]
    price: Optional[str]
    poster_url: Optional[str]
    url: Optional[str]
    venue: VenueOut
    bands: List[BandOut]
    class Config:
        from_attributes = True
