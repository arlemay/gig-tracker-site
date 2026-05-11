"""
Import events from the IG-scraped JSON format:
  { "account": ..., "venue": ..., "events": [ { "code", "date", "title",
    "type", "start_time", "entry", "headliner"?, "supports"?: [...],
    "bands"?: [...], ... }, ... ] }

- Venue matched by name (case-insensitive prefix); created as stub if missing.
- Band handles: @-prefix stripped → used as instagram field; name = stripped handle.
  Plain names (no @) used as-is.
- Idempotent: skips events with matching title + date.
- URL set to https://www.instagram.com/p/<code>/
"""
import argparse, json, os, sys
from datetime import datetime

BALI_LAT, BALI_LON = -8.4095, 115.1889
INSTAGRAM_POST_BASE = "https://www.instagram.com/p/"


def collect_band_tokens(event: dict) -> list[str]:
    """Return all band name/handle tokens from headliner, supports, and bands fields."""
    tokens: list[str] = []
    headliner = event.get("headliner")
    if headliner:
        tokens.append(headliner)
    tokens.extend(event.get("supports") or [])
    tokens.extend(event.get("bands") or [])
    return tokens


def resolve_band(db, Band, token: str):
    """Find or create a Band from a raw token (@handle or plain name)."""
    is_handle = token.startswith("@")
    ig = token.lstrip("@") if is_handle else None
    name = token.lstrip("@")

    band = None
    if ig:
        band = db.query(Band).filter(Band.instagram.ilike(ig)).first()
    if not band:
        band = db.query(Band).filter(Band.name.ilike(name)).first()
    if not band:
        band = Band(name=name, instagram=ig)
        db.add(band)
        db.flush()
        print(f"  NEW BAND: '{name}'" + (f" (@{ig})" if ig else ""))
    return band


def main():
    ap = argparse.ArgumentParser(description="Import events from IG-scraped JSON into bali_gigs.db")
    ap.add_argument("json_path", help="Path to events JSON")
    ap.add_argument("--dry-run", action="store_true", help="Parse only; do not write DB")
    args = ap.parse_args()

    if not os.path.exists(args.json_path):
        print(f"File not found: {args.json_path}", file=sys.stderr)
        sys.exit(1)

    from .database import Base, engine, SessionLocal
    from .models import Band, Venue, Event

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    created = skipped = 0

    try:
        with open(args.json_path, encoding="utf-8") as f:
            data = json.load(f)

        venue_name_raw: str = data.get("venue", "")
        # Strip trailing parenthetical like ", Pererenan (near Canggu)"
        venue_name_short = venue_name_raw.split(",")[0].strip()

        venue = db.query(Venue).filter(Venue.name.ilike(f"%{venue_name_short}%")).first()
        if not venue:
            print(f"  NEW VENUE (stub, needs coords): '{venue_name_short}'")
            venue = Venue(
                name=venue_name_short,
                lat=BALI_LAT,
                lon=BALI_LON,
            )
            db.add(venue)
            db.flush()
        else:
            print(f"  Venue matched: '{venue.name}' (id={venue.id})")

        for ev_data in data.get("events", []):
            title: str = ev_data.get("title", "").strip()
            date_str: str = ev_data.get("date", "")
            start_time: str = ev_data.get("start_time", "20:00")
            entry: str = ev_data.get("entry", "")
            code: str = ev_data.get("code", "")

            if not title or not date_str:
                print(f"  SKIP (missing title/date): {ev_data}")
                skipped += 1
                continue

            try:
                hour, minute = (int(x) for x in start_time.split(":"))
                starts_at = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=hour, minute=minute)
            except (ValueError, AttributeError):
                print(f"  SKIP bad date/time '{date_str} {start_time}' for '{title}'")
                skipped += 1
                continue

            # Idempotency check: same title + same calendar day
            day_start = starts_at.replace(hour=0, minute=0, second=0)
            day_end = starts_at.replace(hour=23, minute=59, second=59)
            existing = (
                db.query(Event)
                .filter(Event.title == title, Event.starts_at >= day_start, Event.starts_at <= day_end)
                .first()
            )
            if existing:
                print(f"  SKIP already exists: '{title}' on {date_str}")
                skipped += 1
                continue

            bands = [resolve_band(db, Band, t) for t in collect_band_tokens(ev_data)]

            url = f"{INSTAGRAM_POST_BASE}{code}/" if code else None
            price = entry if entry else None

            event = Event(
                title=title,
                starts_at=starts_at,
                venue_id=venue.id,
                price=price,
                url=url,
            )
            event.bands = bands
            db.add(event)
            created += 1
            print(f"  OK: '{title}' on {date_str} @ {venue.name} ({len(bands)} bands)")

        if args.dry_run:
            db.rollback()
            print(f"\n[DRY RUN] Would create: {created} events, skip: {skipped}")
        else:
            db.commit()
            print(f"\nCreated: {created} events, skipped: {skipped}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
