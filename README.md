# Bali Gigs

A local gig listing site for Bali — bands, venues, and events with a map view.

## How it works

The site has two parts:

- **Backend** — a FastAPI app serving a JSON REST API, backed by a SQLite database
- **Frontend** — plain HTML/JS pages served by Nginx, which also reverse-proxies `/api/` to the backend

```
Browser
  │
  ├── GET /            → Nginx serves frontend/index.html  (public listing)
  ├── GET /admin.html  → Nginx serves frontend/admin.html  (admin CRUD UI)
  └── GET/POST /api/*  → Nginx proxies to FastAPI on :8000
```

The public site (`index.html`) shows upcoming events, bands, and a Leaflet map of venues. The admin page (`admin.html`) lets you create, edit, and delete events, bands, and venues — protected by an API key.

---

## Stack

| Layer | Technology |
|---|---|
| API | Python 3.13, FastAPI, Uvicorn |
| Database | SQLite (via SQLAlchemy) |
| Frontend | HTML, Tailwind CSS (CDN), Leaflet.js |
| Web server | Nginx (TLS termination + reverse proxy) |
| Process manager | systemd |

---

## Fresh setup from clone

### 1. Clone the repo

```bash
git clone <repo-url> bali-gigs
cd bali-gigs
```

### 2. Create the Python virtual environment

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..
```

### 3. Create the database

The database is created automatically on first run. To seed it with an empty schema now:

```bash
backend/.venv/bin/python -c "from backend.database import Base, engine; Base.metadata.create_all(bind=engine)"
```

This creates `bali_gigs.db` in the repo root.

### 4. Set up the systemd service

Create `/etc/systemd/system/baligigs-api.service`:

```ini
[Unit]
Description=Bali Gigs FastAPI (Uvicorn)
After=network.target

[Service]
User=<your-user>
WorkingDirectory=/home/<your-user>/bali-gigs
Environment="PATH=/home/<your-user>/bali-gigs/backend/.venv/bin"
ExecStart=/home/<your-user>/bali-gigs/backend/.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
Environment="ADMIN_TOKEN=<choose-a-strong-token>"

[Install]
WantedBy=multi-user.target
```

Enable and start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable baligigs-api
sudo systemctl start baligigs-api
```

### 5. Set up Nginx

Install Nginx if needed: `sudo apt install nginx`

Create `/etc/nginx/sites-available/baligigs`:

```nginx
# HTTP -> HTTPS redirect
server {
    listen 80;
    server_name <your-ip-or-domain>;
    return 301 https://$host$request_uri;
}

# HTTPS
server {
    listen 443 ssl;
    http2 on;
    server_name <your-ip-or-domain>;

    ssl_certificate     /etc/nginx/selfsigned/cert.pem;
    ssl_certificate_key /etc/nginx/selfsigned/key.pem;

    root /home/<your-user>/bali-gigs/frontend;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Connection "";
    }
}
```

Enable the site and reload:

```bash
sudo ln -s /etc/nginx/sites-available/baligigs /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

#### TLS certificate (self-signed for local use)

```bash
sudo mkdir -p /etc/nginx/selfsigned
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/nginx/selfsigned/key.pem \
  -out /etc/nginx/selfsigned/cert.pem
```

For a public domain, use Let's Encrypt (`certbot`) instead.

---

## Restarting after changes

```bash
sudo systemctl restart baligigs-api && sudo systemctl reload nginx
```

---

## Admin UI

Open `/admin.html` in your browser. On first visit, click **Set Admin Token** and enter the token you set in `ADMIN_TOKEN` in the systemd service file.

The token is stored in `sessionStorage` and cleared when you close the tab.

---

## Importing data from CSV

### Events

```bash
backend/.venv/bin/python -m backend.import_events_csv /path/to/events.csv --dry-run
backend/.venv/bin/python -m backend.import_events_csv /path/to/events.csv
```

Expected CSV columns: `Show, Date, Promoter, Venue, Address / Notes, Instagram name, Bands, Instgram link`

- **Date** format: `MM/DD/YYYY` — time defaults to 20:00
- **Bands** column accepts comma-separated names or space-separated `@instagram` handles
- Venues not found by name are created as stubs with placeholder coordinates — update lat/lon in the admin UI afterwards
- Re-running is safe (skips events with the same title + date)

### Bands

```bash
backend/.venv/bin/python -m backend.import_bands_csv /path/to/bands.csv
```

Expected CSV columns: `band, genre, country, city`

### Venues

```bash
backend/.venv/bin/python -m backend.import_venues_csv /path/to/venues.csv
```

---

## Map tiles

The map uses [Thunderforest](https://www.thunderforest.com/) tiles. The API key is in `frontend/index.html`. Thunderforest keys are intended to be used client-side but should be **domain-locked** in the Thunderforest dashboard to prevent abuse.

---

## Project structure

```
bali-gigs/
├── backend/
│   ├── main.py               # FastAPI routes
│   ├── models.py             # SQLAlchemy models (Band, Venue, Event)
│   ├── schemas.py            # Pydantic schemas
│   ├── database.py           # DB engine + session setup
│   ├── auth.py               # Admin token auth
│   ├── import_events_csv.py  # CLI: bulk import events
│   ├── import_bands_csv.py   # CLI: bulk import bands
│   ├── import_venues_csv.py  # CLI: bulk import venues
│   ├── requirements.txt
│   └── .venv/
├── frontend/
│   ├── index.html            # Public listing (events, bands, map)
│   └── admin.html            # Admin CRUD UI
└── bali_gigs.db              # SQLite database (not in git)
```

---

## Data model

```
Band         — name, genre, city, instagram, youtube, description
Venue        — name, address, district, lat, lon, instagram, website, notes
Event        — title, starts_at, ends_at, price, poster_url, url
               → belongs to one Venue
               → has many Bands (many-to-many)
```
