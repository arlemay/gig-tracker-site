from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, joinedload

from .database import Base, engine, SessionLocal
from .models import Band, Venue, Event
from .schemas import (
    BandCreate, BandUpdate, BandOut,
    VenueCreate, VenueUpdate, VenueOut,
    EventCreate, EventUpdate, EventOut
)
from .auth import require_admin


app = FastAPI(title="Bali Gigs API")

# --- CORS for local + frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Initialize DB tables
Base.metadata.create_all(bind=engine)


# --- Dependency for DB sessions
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Root healthcheck
@app.get("/")
def root():
    return {"service": "bali-gigs", "status": "ok"}


# ======================
# Bands
# ======================

@app.get("/bands")
def list_bands(db: Session = Depends(get_db)):
    rows = db.query(Band).order_by(Band.name.asc()).all()
    return [
        {
            "id": b.id,
            "name": b.name,
            "genre": b.genre,
            "city": b.city,
            "instagram": b.instagram,
            "youtube": b.youtube,
            "description": b.description,
        }
        for b in rows
    ]


@app.post("/bands", response_model=BandOut, dependencies=[Depends(require_admin)])
def create_band(payload: BandCreate, db: Session = Depends(get_db)):
    if db.query(Band).filter(Band.name == payload.name).first():
        raise HTTPException(status_code=400, detail="Band with this name already exists")
    b = Band(**payload.model_dump())
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


@app.put("/bands/{band_id}", response_model=BandOut, dependencies=[Depends(require_admin)])
def update_band(band_id: int, payload: BandUpdate, db: Session = Depends(get_db)):
    b = db.query(Band).get(band_id)
    if not b:
        raise HTTPException(status_code=404, detail="Band not found")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(b, k, v)
    db.commit()
    db.refresh(b)
    return b


@app.delete("/bands/{band_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_band(band_id: int, db: Session = Depends(get_db)):
    b = db.query(Band).get(band_id)
    if not b:
        raise HTTPException(status_code=404, detail="Band not found")
    db.delete(b)
    db.commit()
    return None


# ======================
# Venues
# ======================

@app.get("/venues")
def list_venues(db: Session = Depends(get_db)):
    rows = db.query(Venue).order_by(Venue.name.asc()).all()
    return [
        {
            "id": v.id,
            "name": v.name,
            "address": v.address,
            "district": v.district,
            "lat": v.lat,
            "lon": v.lon,
            "instagram": v.instagram,
            "website": v.website,
            "notes": v.notes,
        }
        for v in rows
    ]


@app.post("/venues", response_model=VenueOut, dependencies=[Depends(require_admin)])
def create_venue(payload: VenueCreate, db: Session = Depends(get_db)):
    if db.query(Venue).filter(Venue.name == payload.name).first():
        raise HTTPException(status_code=400, detail="Venue with this name already exists")
    v = Venue(**payload.model_dump())
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


@app.put("/venues/{venue_id}", response_model=VenueOut, dependencies=[Depends(require_admin)])
def update_venue(venue_id: int, payload: VenueUpdate, db: Session = Depends(get_db)):
    v = db.query(Venue).get(venue_id)
    if not v:
        raise HTTPException(status_code=404, detail="Venue not found")
    data = payload.model_dump(exclude_unset=True)
    for k, val in data.items():
        setattr(v, k, val)
    db.commit()
    db.refresh(v)
    return v


@app.delete("/venues/{venue_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_venue(venue_id: int, db: Session = Depends(get_db)):
    v = db.query(Venue).get(venue_id)
    if not v:
        raise HTTPException(status_code=404, detail="Venue not found")
    db.delete(v)
    db.commit()
    return None


# ======================
# Events
# ======================

def _apply_event_bands(ev: Event, band_ids, db: Session):
    if band_ids is None:
        return
    bands = db.query(Band).filter(Band.id.in_(band_ids)).all() if band_ids else []
    ev.bands = bands


@app.get("/events")
def list_events(include_past: bool = False, db: Session = Depends(get_db)):
    """List all events. By default, only shows upcoming ones."""
    q = db.query(Event).options(joinedload(Event.venue), joinedload(Event.bands))
    if not include_past:
        now = datetime.now()
        q = q.filter(Event.starts_at >= now)
    rows = q.order_by(Event.starts_at.asc()).all()

    def serialize(e: Event):
        return {
            "id": e.id,
            "title": e.title,
            "starts_at": e.starts_at.isoformat() if e.starts_at else None,
            "ends_at": e.ends_at.isoformat() if e.ends_at else None,
            "price": e.price,
            "poster_url": e.poster_url,
            "url": e.url,
            "venue": {
                "id": e.venue.id if e.venue else None,
                "name": e.venue.name if e.venue else None,
                "lat": e.venue.lat if e.venue else None,
                "lon": e.venue.lon if e.venue else None,
                "address": e.venue.address if e.venue else None,
            },
            "bands": [{"id": b.id, "name": b.name} for b in e.bands],
        }

    return [serialize(e) for e in rows]


@app.post("/events", response_model=EventOut, dependencies=[Depends(require_admin)])
def create_event(payload: EventCreate, db: Session = Depends(get_db)):
    venue = db.query(Venue).get(payload.venue_id)
    if not venue:
        raise HTTPException(status_code=400, detail="Invalid venue_id")

    ev = Event(
        title=payload.title,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        price=payload.price,
        poster_url=payload.poster_url,
        url=payload.url,
        venue_id=payload.venue_id,
    )
    db.add(ev)
    db.flush()
    _apply_event_bands(ev, payload.band_ids, db)
    db.commit()
    db.refresh(ev)
    return db.query(Event).options(joinedload(Event.venue), joinedload(Event.bands)).get(ev.id)


@app.put("/events/{event_id}", response_model=EventOut, dependencies=[Depends(require_admin)])
def update_event(event_id: int, payload: EventUpdate, db: Session = Depends(get_db)):
    ev = db.query(Event).get(event_id)
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found")

    data = payload.model_dump(exclude_unset=True)
    if "venue_id" in data:
        venue = db.query(Venue).get(data["venue_id"])
        if not venue:
            raise HTTPException(status_code=400, detail="Invalid venue_id")

    for k in ["title", "starts_at", "ends_at", "price", "poster_url", "url", "venue_id"]:
        if k in data:
            setattr(ev, k, data[k])
    if "band_ids" in data:
        _apply_event_bands(ev, data["band_ids"], db)

    db.commit()
    db.refresh(ev)
    return db.query(Event).options(joinedload(Event.venue), joinedload(Event.bands)).get(event_id)


@app.delete("/events/{event_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_event(event_id: int, db: Session = Depends(get_db)):
    ev = db.query(Event).get(event_id)
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found")
    ev.bands = []  # detach many-to-many
    db.delete(ev)
    db.commit()
    return None
