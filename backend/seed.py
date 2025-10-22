from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from .database import Base, engine, SessionLocal
from .models import Band, Venue, Event

Base.metadata.create_all(bind=engine)

db: Session = SessionLocal()

# --- Bands (sample)
bands = [
    Band(
        name="Tiny Bunny",
        genre="Indie/Alt",
        city="Denpasar",
        instagram="tiny.bunny.band"
    ),
    Band(
        name="THUMBHXC",
        genre="Hardcore",
        city="Denpasar",
        instagram="thumbhxc"
    ),
]

# --- Venues (sample)
venues = [
    Venue(
        name="Nebula Social Space",
        address="Jl. Tibung Sari, Denpasar",
        district="Denpasar",
        lat=-8.6818,
        lon=115.2040,
        instagram="nebulasocialspace",
        notes="Often hosts local rock/metal nights"
    ),
    Venue(
        name="Jogja Music Corner (Example)",
        address="Kuta (example)",
        district="Badung",
        lat=-8.7237,
        lon=115.1767,
        notes="Sample second venue"
    ),
]

# --- Events (sample)
now = datetime.now()
events = [
    Event(
        title="STREAM 2025: Let It Stream, Let It Scream",
        starts_at=now + timedelta(days=5, hours=19),
        venue=venues[0],
        price="Presale: 50k | OTS: 80k",
        url="https://instagram.com/nebulasocialspace",
        bands=[bands[0]],
    ),
]

# --- Commit all
for x in bands + venues + events:
    db.add(x)

db.commit()
db.close()

print("✅ Seeded sample bands/venues/events.")
