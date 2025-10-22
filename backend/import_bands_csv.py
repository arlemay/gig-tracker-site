import argparse, csv, os, sys
from typing import Optional
from .database import Base, engine, SessionLocal
from .models import Band

def main():
    ap = argparse.ArgumentParser(description="Import bands from CSV into bali_gigs.db")
    ap.add_argument("csv_path", help="Path to CSV with header: band,genre,country,city")
    ap.add_argument("--encoding", default="utf-8", help="File encoding (default: utf-8)")
    ap.add_argument("--delimiter", default=",", help="CSV delimiter (default: ,)")
    ap.add_argument("--dry-run", action="store_true", help="Parse only; do not write DB")
    args = ap.parse_args()

    if not os.path.exists(args.csv_path):
        print(f"CSV not found: {args.csv_path}", file=sys.stderr)
        sys.exit(1)

    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    # Read CSV with header
    with open(args.csv_path, "r", encoding=args.encoding, newline="") as f:
        reader = csv.DictReader(f, delimiter=args.delimiter)
        # normalize header names
        fieldmap = {k.lower().strip(): k for k in reader.fieldnames or []}
        required = ["band", "genre", "country", "city"]
        missing = [r for r in required if r not in fieldmap]
        if missing:
            print(f"CSV header must include: {', '.join(required)}. Missing: {missing}", file=sys.stderr)
            sys.exit(2)

        db = SessionLocal()
        created = updated = skipped = 0
        try:
            for row in reader:
                name = (row[fieldmap["band"]] or "").strip()
                if not name:
                    skipped += 1
                    continue
                genre: Optional[str] = (row[fieldmap["genre"]] or "").strip() or None
                country: Optional[str] = (row[fieldmap["country"]] or "").strip() or None
                city_in: Optional[str] = (row[fieldmap["city"]] or "").strip() or None

                # Choose what to store in Band.city
                city_final = city_in or country

                existing = db.query(Band).filter(Band.name == name).one_or_none()
                if existing:
                    changed = False
                    if genre and genre != existing.genre:
                        existing.genre = genre; changed = True
                    if city_final and city_final != existing.city:
                        existing.city = city_final; changed = True
                    if changed:
                        updated += 1
                    else:
                        skipped += 1
                else:
                    db.add(Band(
                        name=name,
                        genre=genre,
                        city=city_final,
                        instagram=None,
                        youtube=None,
                        description=None
                    ))
                    created += 1

            if args.dry_run:
                db.rollback()
                print(f"[DRY RUN] Would create: {created}, update: {updated}, skip: {skipped}")
            else:
                db.commit()
                print(f"Created: {created}, Updated: {updated}, Skipped: {skipped}")
        finally:
            db.close()

if __name__ == "__main__":
    main()
