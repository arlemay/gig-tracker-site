import argparse, csv, os, sys, json, re, time
from typing import Optional, Dict, Any, List, Tuple
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from .database import Base, engine, SessionLocal
from .models import Venue

# -----------------------------
# Config
# -----------------------------

# Bali bounding box in (lat, lon) pairs: (south_lat, west_lon), (north_lat, east_lon)
BALI_VIEWBOX: Tuple[Tuple[float, float], Tuple[float, float]] = (
    (-8.90, 114.25),
    (-8.00, 115.90),
)

# Common Indonesian address abbreviations
ABBR_MAP = {
    r"\bJl\.?\b": "Jalan",
    r"\bGg\.?\b": "Gang",
    r"\bKec\.?\b": "",           # Kecamatan (subdistrict)
    r"\bKab(\.|upaten)?\b": "",  # Kabupaten/Regency
    r"\bKota\b": "",
    r"\bBar\.\b": "Barat",
    r"\bSel\.\b": "Selatan",
    r"\bUt\.\b": "Utara",
    r"\bTim\.\b": "Timur",
    r"\bRegency\b": "",
}

POSTCODE_RE = re.compile(r"\b\d{5}\b")

# -----------------------------
# Helpers
# -----------------------------

def normalize_address(addr: str) -> str:
    """Normalize and bias the address to Bali, Indonesia for better geocoding."""
    a = (addr or "").strip()
    # strip postal code
    a = POSTCODE_RE.sub("", a)
    # expand/drop abbreviations
    for pat, repl in ABBR_MAP.items():
        a = re.sub(pat, repl, a, flags=re.IGNORECASE)
    # tidy punctuation/spacing
    a = re.sub(r"\s*,\s*", ", ", a)
    a = re.sub(r"\s{2,}", " ", a).strip(", ").strip()
    # ensure Bali & Indonesia present
    if "bali" not in a.lower():
        a += ", Bali"
    if "indonesia" not in a.lower():
        a += ", Indonesia"
    return a

def clean_instagram(handle: Optional[str]) -> Optional[str]:
    if not handle:
        return None
    h = handle.strip()
    if h.startswith("@"):
        h = h[1:]
    return re.sub(r"/+$", "", h) or None

def resolve_website(insta_link: Optional[str]) -> Optional[str]:
    if not insta_link:
        return None
    u = insta_link.strip()
    return u if re.match(r"^https?://", u, flags=re.I) else None

def geocode_bali(geocode, cache: Dict[str, Any], raw_address: str, tries: int = 2, sleep: float = 0.8) -> Optional[Dict[str, float]]:
    """Try multiple Bali-biased candidate strings; cache results."""
    key = (raw_address or "").strip()
    if key in cache:
        return cache[key]

    candidates: List[str] = []
    norm = normalize_address(raw_address)
    candidates.append(norm)

    # fallback 1: keep venue + first locality piece only
    parts = [p.strip() for p in norm.split(",") if p.strip()]
    if len(parts) >= 2:
        c1 = ", ".join(parts[:2])
        if c1.lower() != norm.lower():
            candidates.append(c1)

    # fallback 2: name-only + ", Bali, Indonesia"
    name_only = parts[0] if parts else (raw_address or "").split(",")[0]
    c2 = f"{name_only}, Bali, Indonesia"
    if c2.lower() not in [x.lower() for x in candidates]:
        candidates.append(c2)

    for cand in candidates:
        for _ in range(tries):
            loc = geocode(
                cand,
                exactly_one=True,
                country_codes="id",
                viewbox=BALI_VIEWBOX,   # (lat, lon) pairs
                bounded=True,
                addressdetails=False,
            )
            if loc:
                res = {"lat": float(loc.latitude), "lon": float(loc.longitude)}
                cache[key] = res
                return res
            time.sleep(sleep)
    return None

# -----------------------------
# Main importer
# -----------------------------

def main():
    ap = argparse.ArgumentParser(description="Import venues from CSV (Header: Venue, Address / Notes, Instagram name, Instgram link)")
    ap.add_argument("csv_path", help="Path to CSV")
    ap.add_argument("--encoding", default="utf-8")
    ap.add_argument("--delimiter", default=",")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--cache", default="geocode_cache.json")
    ap.add_argument("--sleep", type=float, default=1.0, help="Seconds between geocoder calls (be nice to Nominatim)")
    args = ap.parse_args()

    if not os.path.exists(args.csv_path):
        print(f"CSV not found: {args.csv_path}", file=sys.stderr)
        sys.exit(1)

    Base.metadata.create_all(bind=engine)

    # Load geocode cache
    cache: Dict[str, Any] = {}
    if os.path.exists(args.cache):
        try:
            with open(args.cache, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            cache = {}

    # Read CSV
    with open(args.csv_path, "r", encoding=args.encoding, newline="") as f:
        reader = csv.DictReader(f, delimiter=args.delimiter)
        headers = [h.strip() for h in (reader.fieldnames or [])]

        # Your sample shows: "Venue,Address / Notes,Instagram name, Instgram link"
        wanted = ["Venue", "Address / Notes", "Instagram name", " Instgram link"]
        # Some sheets omit the leading space before Instgram link
        if "Instgram link" in headers and " Instgram link" not in headers:
            wanted[-1] = "Instgram link"

        for w in wanted:
            if w not in headers:
                print(f"CSV header missing required column: {w}\nHeaders found: {headers}", file=sys.stderr)
                sys.exit(2)

        geolocator = Nominatim(user_agent="bali-gigs-importer")
        geocode = RateLimiter(geolocator.geocode, min_delay_seconds=args.sleep)

        db = SessionLocal()
        created = updated = skipped = failed = 0
        try:
            for row in reader:
                name = (row.get("Venue") or "").strip()
                address = (row.get("Address / Notes") or "").strip()
                insta_name = clean_instagram(row.get("Instagram name"))
                insta_link = (row.get(" Instgram link") or row.get("Instgram link") or "").strip()

                if not name or not address:
                    skipped += 1
                    continue

                loc = geocode_bali(geocode, cache, address, tries=2, sleep=args.sleep)
                if not loc:
                    print(f"[WARN] Could not geocode: {name} | {address}", file=sys.stderr)
                    failed += 1
                    continue

                website = resolve_website(insta_link)

                existing: Optional[Venue] = db.query(Venue).filter(Venue.name == name).one_or_none()
                if existing:
                    changed = False
                    if existing.address != address:
                        existing.address = address; changed = True
                    if existing.lat != loc["lat"] or existing.lon != loc["lon"]:
                        existing.lat, existing.lon = loc["lat"], loc["lon"]; changed = True
                    if existing.instagram != insta_name:
                        existing.instagram = insta_name; changed = True
                    if website and existing.website != website:
                        existing.website = website; changed = True
                    if changed:
                        updated += 1
                    else:
                        skipped += 1
                else:
                    v = Venue(
                        name=name,
                        address=address,
                        district=None,  # optional; parse later if needed
                        lat=loc["lat"],
                        lon=loc["lon"],
                        instagram=insta_name,
                        website=website,
                        notes=None
                    )
                    db.add(v)
                    created += 1

            # Save cache
            try:
                with open(args.cache, "w", encoding="utf-8") as f:
                    json.dump(cache, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"[WARN] Failed to write cache: {e}", file=sys.stderr)

            if args.dry_run:
                db.rollback()
                print(f"[DRY RUN] Create: {created}, Update: {updated}, Skip: {skipped}, Geocode-failed: {failed}")
            else:
                db.commit()
                print(f"Created: {created}, Updated: {updated}, Skipped: {skipped}, Geocode-failed: {failed}")
        finally:
            db.close()

if __name__ == "__main__":
    main()
