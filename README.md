# Tender Trail

**Government Tender Scraper and Buying Opportunity Notifier**

Tender Trail scrapes Indian government tender/e-procurement sources, normalizes
and stores them in MongoDB, and gives business users a searchable dashboard,
a saved-watchlist + email alert system, and a full REST API — all built on
Django + Django REST Framework.

---

## Features

- **Multi-portal scraping** — `data.gov.in`, `eProcure.gov.in` (CPPP), and
  per-state portal scrapers, all run concurrently with `concurrent.futures`
  threads. Every scraper fails over to realistic sample data if a live
  endpoint is unreachable or requires an API key, so the app always has
  something to show.
- **Parsing & validation** — regex extraction/validation of tender reference
  numbers (`ABC/2025/1234`-style patterns), `datetime`-based deadline
  normalization from several source formats.
- **Filtering utilities** — category/state/deadline filtering built with
  list comprehensions and tuples (`scraper/parser.py`).
- **MongoDB storage** — tenders, saved watchlists, and alert preferences are
  MongoEngine documents with full CRUD, indexed for fast category/state/
  deadline queries.
- **Django dashboard** — responsive Tailwind + DaisyUI UI: stat cards,
  Chart.js deadline/category charts, advanced filter sidebar, tender cards,
  CSV export, pagination.
- **Alert engine** — per-user preferences (categories, states, days-before
  reminders); sends email reminders (or logs to console if no SMTP is
  configured) using `threading` to fan out across users.
- **DRF REST API** — JWT-authenticated endpoints for tenders, watchlists,
  alert preferences, and dashboard stats.
- **Auth** — registration/login for saving watchlists & preferences.
- **Management commands** — `run_scraper`, `send_alerts`, `seed_data`.
- **Docker** — `docker-compose.yml` wires up MongoDB, the Django web app,
  and a background scraper worker container.

---

## Project layout

```
tender_trail/
├── tender_trail/          # Django project settings, urls, wsgi/asgi
├── tenders/                # Tender/Watch/AlertPreference MongoEngine models,
│                            #   dashboard views, DRF serializers/views, forms
├── scraper/                 # Scraper classes, parser/regex, threaded
│                            #   coordinator, alert engine, management commands
├── users/                   # Registration/login views + DRF registration
├── templates/                # Django templates (Tailwind + DaisyUI)
├── static/                    # custom CSS/JS (Tailwind loaded via CDN)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## Quick start (local, without Docker)

1. **Install MongoDB** locally (or point `.env` at a hosted instance / the
   `docker-compose` mongo service).

2. **Create a virtualenv and install dependencies:**
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure environment:**
   ```bash
   cp .env.example .env
   # edit .env — set DJANGO_SECRET_KEY, MONGO_HOST, email creds, etc.
   ```

4. **Run Django migrations** (for the relational auth/session tables):
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

5. **Seed sample tender data** (no network required):
   ```bash
   python manage.py seed_data --count 60
   ```
   Or run the real (multi-threaded) scraper, which falls back to sample
   data automatically for any portal it can't reach:
   ```bash
   python manage.py run_scraper
   ```

6. **Start the dev server:**
   ```bash
   python manage.py runserver
   ```
   Visit `http://127.0.0.1:8000/` for the dashboard and `/admin/` for the
   Django admin (auth/session management).

7. **Send deadline alert emails** (simulated on console unless SMTP is
   configured in `.env`):
   ```bash
   python manage.py send_alerts
   ```

---

## Quick start (Docker)

```bash
cp .env.example .env
docker compose up --build
```

This starts:
- `mongo` — MongoDB 7
- `web` — Django + Gunicorn on `http://localhost:8000`
- `scraper` — a background worker looping `run_scraper` every
  `SCRAPER_INTERVAL_HOURS`

Then, in another terminal:
```bash
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py seed_data --count 60
```

---

## REST API

All endpoints are under `/api/`.

| Method | Endpoint                       | Description                          |
|--------|---------------------------------|---------------------------------------|
| GET    | `/api/tenders/`                 | List/filter tenders (`category`, `state`, `status`, `min_value`, `max_value`, `deadline_before`, `q`, `ordering`, `page`, `page_size`) |
| POST   | `/api/tenders/`                 | Create a tender (auth required)       |
| GET    | `/api/tenders/<id>/`            | Tender detail                         |
| PUT    | `/api/tenders/<id>/`            | Update a tender (auth required)       |
| DELETE | `/api/tenders/<id>/`            | Delete a tender (auth required)       |
| GET    | `/api/watches/`                 | List your saved watches (auth)        |
| POST   | `/api/watches/`                 | Create a saved watch (auth)           |
| DELETE | `/api/watches/<id>/`            | Remove a saved watch (auth)           |
| GET/PUT| `/api/alert-preferences/`       | View/update your alert settings (auth)|
| GET    | `/api/stats/`                   | Dashboard analytics payload           |
| POST   | `/api/auth/register/`           | Create a new account                  |
| POST   | `/api/token/`                   | Obtain a JWT access/refresh token pair|
| POST   | `/api/token/refresh/`           | Refresh a JWT access token            |

Example:
```bash
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "demo", "password": "yourpassword"}'

curl "http://localhost:8000/api/tenders/?category=IT%20%26%20Software&state=Maharashtra" \
  -H "Authorization: Bearer <access_token>"
```

---

## Notes on the MongoDB + Django setup

Django's auth/session/admin system is relational by nature, so this project
keeps `django.contrib.auth` on SQLite (swap for Postgres in production via
`DATABASES` in `settings.py`) while all tender/watchlist/alert-preference
data lives in MongoDB via MongoEngine, connected once in `settings.py`.
Watches and alert preferences reference the Django user by numeric
`user_id` rather than a Mongo-native relation.

## Extending to more portals

Add a new `BaseScraper` subclass in `scraper/scrapers.py` implementing
`_fetch_live()` and `_sample_fallback()`, then include an instance of it in
`get_default_scrapers()`. The threaded coordinator (`scraper/threading_utils.py`)
picks it up automatically on the next `run_scraper` run.
