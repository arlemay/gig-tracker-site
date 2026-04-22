"""
Import events from a CSV with columns:
  Show, Date, Promoter, Venue, Address / Notes, Instagram name, Bands, Instgram link

- Venues are matched case-insensitively; created as stubs (Bali centre coords) if missing.
- Bands column accepts two formats:
    @handle1 @handle2 ...      (space-separated Instagram handles)
    Name One, Name Two, ...    (comma-separated display names)
  Bands are matched by name or instagram handle; created if not found.
- Events with an identical title + date are skipped (idempotent re-runs).
- Time defaults to 20:00 local when not in the CSV.
"""
import argparse, csv, os, re, sys
from datetime import datetime

BALI_LAT, BALI_LON = -8.4095, 115.1889
DEFAULT_HOUR = 20


def parse_bands(raw: str) -> list[str]:
    """Return a list of cleaned band name/handle strings."""
    raw = raw.strip()
    if not raw:
        return []
    if "@" in raw and "," not in raw:
        # Space-separated @handles — strip the @ to use as name
        parts = raw.split()
        return [p.lstrip("@").strip() for p in parts if p.strip()]
    # Comma-separated names
    return [p.strip() for p in raw.split(",") if p.strip()]


def clean_venue_name(raw: str) -> str:
    """Strip trailing parenthetical instagram handles from venue names."""
    return re.sub(r"\s*\(@[^)]*\)\s*$", "", raw).strip()


def main():
    ap = argparse.ArgumentParser(description="Import events from CSV into bali_gigs.db")
    ap.add_argument("csv_path", help="Path to events CSV")
    ap.add_argument("--dry-run", action="store_true", help="Parse only; do not write DB")
    ap.add_argument("--time", default=str(DEFAULT_HOUR), help="Default event hour when not in CSV (default: 20)")
    args = ap.parse_args()

    if not os.path.exists(args.csv_path):
        print(f"CSV not found: {args.csv_path}", file=sys.stderr)
        sys.exit(1)

    default_hour = int(args.time)

    # Import here so the script can run as a module from the repo root
    from .database import Base, engine, SessionLocal
    from .models import Band, Venue, Event

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    created = skipped = 0
    venue_warnings: list[str] = []

    try:
        with open(args.csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            # Normalise header names (strip whitespace, lowercase)
            headers = {k.strip().lower(): k for k in (reader.fieldnames or [])}

            def col(row, *candidates):
                for c in candidates:
                    if c in headers:
                        return (row.get(headers[c]) or "").strip()
                return ""

            for row in reader:
                title = col(row, "show")
                date_str = col(row, "date")
                venue_raw = col(row, "venue")
                address = col(row, "address / notes")
                venue_ig = col(row, "instagram name").lstrip("@")
                bands_raw = col(row, "bands")
                url = col(row, "instgram link", "instagram link") or None

                if not title or not date_str:
                    print(f"  SKIP (no title/date): {row}")
                    skipped += 1
                    continue

                # Parse date
                try:
                    starts_at = datetime.strptime(date_str, "%m/%d/%Y").replace(hour=default_hour)
                except ValueError:
                    print(f"  SKIP bad date '{date_str}' for event '{title}'")
                    skipped += 1
                    continue

                # Idempotency: skip if same title + same date already exists
                existing_event = (
                    db.query(Event)
                    .filter(
                        Event.title == title,
                        Event.starts_at >= starts_at.replace(hour=0, minute=0, second=0),
                        Event.starts_at < starts_at.replace(hour=23, minute=59, second=59),
                    )
                    .first()
                )
                if existing_event:
                    print(f"  SKIP already exists: '{title}' on {date_str}")
                    skipped += 1
                    continue

                # Resolve venue
                venue_name = clean_venue_name(venue_raw)
                venue = db.query(Venue).filter(
                    Venue.name.ilike(f"%{venue_name}%")
                ).first() if venue_name else None

                if not venue and venue_name:
                    print(f"  NEW VENUE (stub, needs coords): '{venue_name}'")
                    venue_warnings.append(venue_name)
                    venue = Venue(
                        name=venue_name,
                        address=address or None,
                        lat=BALI_LAT,
                        lon=BALI_LON,
                        instagram=venue_ig or None,
                    )
                    db.add(venue)
                    db.flush()
                elif not venue:
                    print(f"  SKIP no venue for event '{title}'")
                    skipped += 1
                    continue

                # Resolve bands
                band_names = parse_bands(bands_raw)
                bands: list[Band] = []
                for bname in band_names:
                    band = (
                        db.query(Band).filter(Band.name.ilike(bname)).first()
                        or db.query(Band).filter(Band.instagram.ilike(bname)).first()
                    )
                    if not band:
                        band = Band(name=bname)
                        db.add(band)
                        db.flush()
                        print(f"  NEW BAND: '{bname}'")
                    bands.append(band)

                ev = Event(
                    title=title,
                    starts_at=starts_at,
                    url=url,
                    venue_id=venue.id,
                )
                ev.bands = bands
                db.add(ev)
                created += 1
                print(f"  OK: '{title}' on {date_str} @ {venue.name} ({len(bands)} bands)")

        if args.dry_run:
            db.rollback()
            print(f"\n[DRY RUN] Would create: {created} events, skip: {skipped}")
        else:
            db.commit()
            print(f"\nCreated: {created} events, skipped: {skipped}")

        if venue_warnings:
            print(f"\nWARNING: {len(venue_warnings)} new venue(s) created with placeholder coords.")
            print("Update their lat/lon in the admin UI:")
            for v in venue_warnings:
                print(f"  - {v}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
